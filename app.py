from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import uuid
import sqlite3
import reportlab

# OCR imports
try:
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor
    DOCTR_AVAILABLE = True
except:
    DOCTR_AVAILABLE = False

# Transformers for AI
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch

from models.cbc_parser import extract_cbc_clean, assess_cbc
from models.database import CBCDatabase

def extract_text_with_pytesseract(file_path):
    """Alternative OCR using pytesseract"""
    if not PYTESSERACT_AVAILABLE:
        return None, "pytesseract not available"
    
    try:
        if file_path.lower().endswith('.pdf'):
            if not PDF_SUPPORT:
                return None, "PDF support not available. Install pdf2image"
            # Convert PDF to images
            images = convert_from_path(file_path)
            text = ""
            for image in images:
                text += pytesseract.image_to_string(image) + "\n"
            return text, None
        else:
            # Process image
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            return text, None
    except Exception as e:
        return None, str(e)


def extract_text_from_file(file_path):
    """Extract text using available OCR method"""
    
    # Try doctr first (best quality)
    if DOCTR_AVAILABLE:
        try:
            model = get_ocr_model()
            if file_path.lower().endswith('.pdf'):
                doc = DocumentFile.from_pdf(file_path)
            else:
                doc = DocumentFile.from_images(file_path)
            
            result = model(doc)
            text = result.render()
            return text, None
        except Exception as e:
            print(f"doctr failed: {e}, trying alternative...")
    
    # Fallback to pytesseract
    if PYTESSERACT_AVAILABLE:
        return extract_text_with_pytesseract(file_path)
    
    # No OCR available
    return None, "No OCR engine available. Please install: pip install python-doctr[torch] OR pip install pytesseract"

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db = CBCDatabase()

# Initialize OCR model (lazy loading)
ocr_model = None

def get_ocr_model():
    global ocr_model
    if ocr_model is None and DOCTR_AVAILABLE:
        ocr_model = ocr_predictor(pretrained=True)
    return ocr_model

# Initialize BioGPT model (lazy loading)
bio_model = None
bio_tokenizer = None

def get_bio_model():
    global bio_model, bio_tokenizer
    if bio_model is None:
        try:
            # Using microsoft/biogpt for medical domain
            bio_tokenizer = AutoTokenizer.from_pretrained("microsoft/biogpt")
            bio_model = AutoModelForCausalLM.from_pretrained("microsoft/biogpt")
            print("BioGPT model loaded successfully")
        except Exception as e:
            print(f"Error loading BioGPT: {e}")
            # Fallback to a smaller model
            try:
                bio_tokenizer = AutoTokenizer.from_pretrained("distilgpt2")
                bio_model = AutoModelForCausalLM.from_pretrained("distilgpt2")
                print("Fallback to DistilGPT2")
            except Exception as e2:
                print(f"Error loading fallback model: {e2}")
    return bio_model, bio_tokenizer


def extract_text_from_file(file_path):
    """Extract text using OCR"""
    if not DOCTR_AVAILABLE:
        return None, "OCR not available. Install python-doctr[torch]"
    
    try:
        model = get_ocr_model()
        if file_path.lower().endswith('.pdf'):
            doc = DocumentFile.from_pdf(file_path)
        else:
            doc = DocumentFile.from_images(file_path)
        
        result = model(doc)
        text = result.render()
        return text, None
    except Exception as e:
        return None, str(e)


def generate_ai_response(question, cbc_data, assessment):
    """Generate response based on actual extracted CBC data."""
        # 🩺 Check if the user is asking about overall report status
    q_lower = question.lower().strip()
    
    # --- Add this block for worry/concern-related questions ---
    concern_phrases = [
        "should i worry", "is this serious", "is this dangerous",
        "should i fear it", "am i at risk", "is it harmful",
        "is it bad", "is it concerning", "should i be concerned",
        "is this alarming", "is this critical", "is it dangerous",
        "do i need to panic", "should i be worried", "is this a problem",
        "does this indicate something serious", "is it risky",
        "am i in danger", "is this harmful for my health",
        "should i consult a doctor immediately", "is it urgent",
        "do i need medical attention", "is it life threatening",
        "am i okay", "am i healthy", "should i take action",
        "should i be cautious", "is this cause for concern"
    ]
    
    if any(phrase in q_lower for phrase in concern_phrases):
        return get_reassurance_response(q_lower, assessment, param_variations)
    # --- End of block ---
    
    # Existing parameter mapping and checks follow
    param_variations = get_comprehensive_param_mapping()
    
    health_check_phrases = [
        # Common report-related questions
        "are my results good", "is my report good", "is everything normal",
        "are my reports normal", "am i healthy", "is my health okay",
        "how are my results", "how is my report", "is my cbc good",
        "are the results fine", "is everything okay", "are my values okay",
        "are my blood test results okay", "does it look fine",
        "is my report okay", "are my results fine", "is my blood test normal",
        "are my blood results good", "is my cbc normal", "is my report fine",
        "are my readings normal", "are my numbers normal",
        "are my counts good", "are my blood levels good",
        "is my health report fine", "is my blood normal",
        "does my report look normal", "am i fine", "am i doing okay",
        "does my health look okay", "does everything look okay",
        "are my readings good", "does it seem normal", "are things normal",
        "does my cbc look good", "are my test results normal",
        "is my blood report okay", "is my cbc fine", "are my cbc values okay",
        "is my cbc report okay", "is my test result good", "am i all right",
        "is my report positive", "is my report negative", "is my blood okay",
        "are there any issues in my report", "is my report clear",
        "is my report showing anything bad", "is my blood fine",
        "am i perfectly healthy", "is everything fine with my report",
        "is my cbc test okay", "is my cbc test normal", "is my health normal",
        "is my blood test fine", "does my test look fine",
        "am i doing well health wise", "are my medical results fine",
        "are my test results fine", "are my results okay"
    ]


    q_lower = question.lower().strip()
    if any(phrase in q_lower for phrase in health_check_phrases):
        try:
            # If assessment data is available, respond based on it
            if assessment and isinstance(assessment, dict):
                abnormal = [
                    k for k, v in assessment.items()
                    if "abnormal" in str(v).lower() or "high" in str(v).lower() or "low" in str(v).lower()
                ]
                if abnormal:
                    return (
                        f"Your report shows some values that need attention ⚠️ — "
                        f"{', '.join(abnormal[:3])}{' and more' if len(abnormal) > 3 else ''}.\n\n"
                        "It's not necessarily serious, but you should discuss these with your doctor "
                        "to understand them better. Would you like me to explain any of these values?"
                    )
                else:
                    return (
                        "Everything in your CBC report looks normal! 🎉\n"
                        "Your blood parameters are within healthy ranges — great job keeping yourself healthy! 💪"
                    )
            else:
                return (
                    "I can help you check if your CBC results look good. 🩸 "
                    "Could you upload or provide your CBC data so I can review it?"
                )
        except Exception:
            return (
                "I couldn’t analyze your report fully, but I can explain your CBC results. "
                "Please upload your report or share your readings!"
            )

        # --- Handle greetings and casual conversation ---
    casual_phrases = {
        # 👋 Greetings & Small Talk
        "hi": "Hi there! 👋 How can I help you understand your CBC report today?",
        "hello": "Hello! 😊 I’m your CBC Assistant bot. Ask me about any of your report values.",
        "hey": "Hey! 👋 I can help explain what your blood test results mean.",
        "how are you": "I’m doing great, thanks for asking! 🤖 How about you? Would you like to discuss your CBC results?",
        "how are you doing": "I’m feeling fantastic! 😊 Ready to help you understand your CBC report.",
        "good morning": "Good morning! ☀️ Hope you’re feeling healthy today.",
        "good afternoon": "Good afternoon! 🌤 Let’s go through your CBC report together.",
        "good evening": "Good evening! 🌙 How can I assist you with your blood report today?",
        "good night": "Good night! 🌙 Remember to rest well — it helps your body recover.",
        "yo": "Hey there! 👋 Need help with your CBC report?",
        "what’s up": "Not much, just here to help you understand your blood report! 😄",
        "sup": "Hey! 👋 What can I help you with today?",

        # 🙏 Gratitude & Appreciation
        "thank you": "You're welcome! 💙 I'm glad to help you understand your health better.",
        "thanks": "No problem! 😊 Happy to help you with your report.",
        "thank u": "You’re most welcome! 💙",
        "thanks a lot": "You’re very welcome! Always happy to help. 😊",
        "thank you so much": "It’s my pleasure! 💙 Glad I could help you out.",
        "appreciate it": "Glad to hear that! 😊 Let me know if you’d like to understand more about your results.",

        # 🌟 Compliments
        "you are great": "Aww, thank you! 🤖 I'm here to make health information easier for you.",
        "you’re awesome": "Thank you! 💙 I’m just doing my job — helping you stay informed!",
        "good bot": "Thanks! 😄 I appreciate that.",
        "nice work": "Thanks! 😊 Glad you liked it.",
        "well done": "Thank you! 💪 Let’s keep understanding your health together.",

        # 👋 Farewells
        "bye": "Goodbye! 👋 Take care and stay healthy.",
        "see you": "See you later! 👋 Stay safe and healthy!",
        "talk to you later": "Sure thing! I’ll be here whenever you need help with your CBC report.",
        "goodbye": "Goodbye! 💙 Take care of your health.",

        # 👍 Affirmations & Acknowledgments
        "ok": "Got it! 👍 Let’s continue.",
        "okay": "Okay! 😊 What would you like to know next?",
        "sure": "Sure thing! 🤖 I’m ready to help.",
        "yes": "Yes! 😊 Please go ahead with your question.",
        "yep": "Yep! 👍 I’m here and ready.",
        "yeah": "Yeah! Let’s continue exploring your report.",
        "alright": "Alright! 😊 Let’s get started.",
        "fine": "Glad to hear that! 💙 How can I assist you?",
        "cool": "Cool 😎 Let’s move ahead.",
        "great": "Awesome! 💪 What’s your next question?",
        "perfect": "Perfect! 🤖 Let’s continue.",
        "no": "No worries! 😊 Let me know if you change your mind.",
        "not really": "That’s okay! 💙 I can still help if you’d like to know something specific."
    }

    q_lower = question.lower().strip()
    for phrase, response in casual_phrases.items():
        if phrase in q_lower:
            return response

    try:
        return generate_enhanced_rule_based_response(question, cbc_data, assessment)
    except Exception as e:
        print(f"Error in AI response: {e}")
        return "I'm here to help you understand your CBC report. Please ask me about your specific results!"


# ✅ Centralized rule-based explanations for CBC parameters
cbc_explanations = {
    "LYMPHOCYTES": lambda data: f"""**Your lymphocyte count is a bit high** ({data['value']:.2f} {data.get('unit', '')})

High lymphocytes usually indicate your immune system is active:

**🔍 Common Causes:**
• Viral infection (most common)
• Recovery from infection
• Chronic infections
• Smoking or stress
• Rarely: blood disorders

**🩺 What to do:**
• Get plenty of rest  
• Stay hydrated  
• Eat nutritious foods  
• Manage stress  
• Avoid smoking  

**👨‍⚕️ Medical Follow-up:**
• Discuss with your doctor  
• Often resolves as you recover from illness  

High lymphocytes usually normalize as your immune system recovers. 💙""",

    "MONOCYTES": lambda data: f"""**Your monocyte count is a bit high** ({data['value']:.2f} {data.get('unit', '')})

High monocytes suggest your body is handling inflammation or infection.

**🔍 Common Causes:**
• Chronic inflammation  
• Autoimmune conditions  
• Recovery from infection  
• Stress  

**🥗 Supportive Steps:**
• Eat anti-inflammatory foods (fish, berries, greens)  
• Regular sleep & hydration  
• Reduce processed foods  

**👨‍⚕️ Medical Follow-up:**
• Doctor may monitor for inflammation  
• Often improves with a healthy lifestyle 💙""",

    "EOSINOPHILS": lambda data: f"""**Your eosinophil count is a bit high** ({data['value']:.2f} {data.get('unit', '')})

Often related to allergies or parasitic conditions.

**🔍 Common Causes:**
• Allergies or asthma  
• Skin conditions (eczema, psoriasis)  
• Certain medications  
• Parasitic infections  

**🩺 What to do:**
• Identify and avoid triggers  
• Use allergy meds if prescribed  
• Eat anti-inflammatory foods  
• Stay hydrated  

Usually manageable and improves with allergy treatment. 💙""",

    "BASOPHILS": lambda data: f"""**Your basophil count is a bit high** ({data['value']:.2f} {data.get('unit', '')})

Usually linked to allergic or inflammatory responses.

**🔍 Causes:**
• Allergic reactions  
• Thyroid disorders  
• Chronic inflammation  

**👨‍⚕️ Follow-up:**
• Discuss with your doctor  
• May need thyroid or allergy testing  
• Usually monitored over time 💙""",

    "HEMATOCRIT": lambda data: f"""**Your hematocrit is high** ({data['value']:.2f} {data.get('unit', '')})

Means your blood is thicker than normal.

**💧 Stay Hydrated:**
• Drink 8–10 glasses of water per day  
• Avoid dehydration (common cause)  

**🔍 Other Causes:**
• Smoking  
• High altitude living  
• Sleep apnea  
• Kidney or lung disease  

**👨‍⚕️ Medical Follow-up:**
• Doctor may suggest tests for oxygen levels  
• Often improves with hydration and lifestyle 💙""",

    "MCV": lambda data: f"""**Your MCV is high** ({data['value']:.2f} {data.get('unit', '')})

Large red blood cells indicate possible vitamin deficiency.

**🔍 Common Causes:**
• Vitamin B12 or folate deficiency  
• Alcohol use  
• Liver or thyroid issues  

**🥗 Nutrition:**
• Eat leafy greens, fish, eggs, fortified cereals  
• Limit alcohol  

**👨‍⚕️ Follow-up:**
• Doctor may check B12 & folate levels  
• Treat with supplements if needed 💙""",

    "MCH": lambda data: f"""**Your MCH is high** ({data['value']:.2f} {data.get('unit', '')})

Shows more hemoglobin per red cell — often linked with high MCV.

**🔍 Causes:**
• B12 or folate deficiency  
• Certain medications  

**🥗 Nutrition:**
• Eat B12- and folate-rich foods  
• Follow doctor’s advice on supplementation 💙""",

    "MCHC": lambda data: f"""**Your MCHC is high** ({data['value']:.2f} {data.get('unit', '')})

This is rare and may indicate a red cell disorder.

**🔍 Possible Causes:**
• Hereditary spherocytosis  
• Autoimmune hemolytic anemia  
• Severe burns  
• Lab error  

**👨‍⚕️ Medical Follow-up:**
• Doctor may repeat test  
• Usually investigated further if persistent 💙""",

    "RDW": lambda data: f"""**Your RDW is high** ({data['value']:.2f} {data.get('unit', '')})

Shows variation in red blood cell size.

**🔍 Common Causes:**
• Iron, B12, or folate deficiency  
• Early or recovering anemia  

**🥗 Supportive Care:**
• Eat iron-rich foods (meat, greens, beans)  
• Ensure vitamin intake  
• Balanced diet  

**👨‍⚕️ Medical Follow-up:**
• Doctor may check nutrient levels  
• Usually improves with proper diet 💙"""
}


# cbc_response_module.py
# Complete, self-contained rule-based response engine for CBC chat UI
# Includes generate_enhanced_rule_based_response and supporting helpers

def generate_enhanced_rule_based_response(question, cbc_data, assessment):
    """Main response generation with comprehensive question handling."""
    question_lower = (question or "").lower().strip()

    # Parameter mapping (all keys should be lowercase)
    param_variations = get_comprehensive_param_mapping()

    # 1. "what to do" questions
    if any(phrase in question_lower for phrase in ["what to do", "what should i do", "what can i do", "how to fix", "how to improve", "what to eat", "how to treat"]):
        response = get_what_to_do_response(question_lower, assessment, param_variations)
        if response:
            return response

    # 2. high/low value questions
    if any(pattern in question_lower for pattern in ["high", "low", "elevated", "decreased", "why is", "what if", "above", "below"]):
        response = get_high_low_advice(question_lower, assessment, param_variations)
        if response:
            return response

    # 3. parameter explanation requests
    if any(word in question_lower for word in ["what is", "explain", "tell me about", "meaning of", "define"]):
        response = get_parameter_explanation(question_lower, assessment, param_variations)
        if response:
            return response

    # 4. "my value" or specific value queries
    if any(word in question_lower for word in ["my", "level", "value", "result", "count", "reading", "score"]):
        response = get_parameter_value_response(question_lower, assessment, param_variations)
        if response:
            return response

    # 5. normal range questions
    if any(term in question_lower for term in ["normal", "range", "reference", "should be"]):
        # if specific param asked, return value; else list normal ranges
        if any(param in question_lower for param in param_variations.keys()):
            response = get_parameter_value_response(question_lower, assessment, param_variations)
            if response:
                return response
        return get_clean_normal_ranges()

    # 6. overall report questions
    if any(term in question_lower for term in ["summary", "overview", "overall", "report", "everything", "all results", "full report"]):
        return get_clean_report_summary(assessment, cbc_data)

    # 7. concern/worry questions
    if any(word in question_lower for word in ["worried", "concern", "dangerous", "serious", "risk", "problem", "should i be"]):
        return get_reassurance_response(question_lower, assessment, param_variations)

    # 8. comparison questions
    if any(word in question_lower for word in ["compare", "difference", "versus", "vs", "better", "worse"]):
        return get_comparison_response(question_lower, assessment, param_variations)

    # 9. general CBC questions
    if "cbc" in question_lower or "complete blood count" in question_lower:
        return get_cbc_general_info(question_lower, assessment)

    # 10. default intelligent response
    return get_smart_guidance_response(question_lower, assessment, cbc_data, param_variations)


def get_comprehensive_param_mapping():
    """Return mapping from many keyword variations (lowercase) to canonical assessment keys."""
    return {
        # Hemoglobin
        "hemoglobin": "HEMOGLOBIN", "hgb": "HEMOGLOBIN", "hb": "HEMOGLOBIN", "haemoglobin": "HEMOGLOBIN",
        # WBC
        "wbc": "TOTAL LEUKOCYTE COUNT", "white blood cell": "TOTAL LEUKOCYTE COUNT", "white blood cells": "TOTAL LEUKOCYTE COUNT",
        "white blood": "TOTAL LEUKOCYTE COUNT", "leukocyte": "TOTAL LEUKOCYTE COUNT", "tlc": "TOTAL LEUKOCYTE COUNT",
        # RBC
        "rbc": "RBC COUNT", "red blood cell": "RBC COUNT", "red blood": "RBC COUNT", "red cell": "RBC COUNT", "erythrocyte": "RBC COUNT",
        # Platelets
        "platelet": "PLATELET COUNT", "plt": "PLATELET COUNT", "thrombocyte": "PLATELET COUNT", "platelets": "PLATELET COUNT",
        # Hematocrit
        "hematocrit": "HEMATOCRIT", "hct": "HEMATOCRIT", "haematocrit": "HEMATOCRIT", "pcv": "HEMATOCRIT",
        # MCV / MCH / MCHC / RDW
        "mcv": "MCV", "mean corpuscular volume": "MCV", "cell size": "MCV",
        "mch": "MCH", "mean corpuscular hemoglobin": "MCH",
        "mchc": "MCHC", "mean corpuscular hemoglobin concentration": "MCHC",
        "rdw": "RDW", "red cell distribution width": "RDW",
        # Differential
        "neutrophil": "NEUTROPHILS", "neut": "NEUTROPHILS", "neutro": "NEUTROPHILS", "polymorph": "NEUTROPHILS", "pmn": "NEUTROPHILS",
        "lymphocyte": "LYMPHOCYTES", "lymph": "LYMPHOCYTES", "lympho": "LYMPHOCYTES",
        "monocyte": "MONOCYTES", "mono": "MONOCYTES",
        "eosinophil": "EOSINOPHILS", "eos": "EOSINOPHILS", "eosino": "EOSINOPHILS",
        "basophil": "BASOPHILS", "baso": "BASOPHILS",
    }


def find_parameter_in_assessment(question_lower, assessment, param_variations):
    """Return (assessment_key, data) if the question mentions a parameter present in assessment."""
    assessed = assessment.get('assessed', {}) if assessment else {}
    for keyword, assessment_key in param_variations.items():
        if keyword in question_lower:
            data = assessed.get(assessment_key)
            if data and data.get('value') is not None:
                return assessment_key, data
    # Try simple fallback: if question explicitly names a canonical key
    for key in assessed.keys():
        if key.lower() in question_lower:
            data = assessed.get(key)
            if data and data.get('value') is not None:
                return key, data
    return None, None


# -------------------------------
# Explanations dictionary (used by recommendation helpers and explicit explanation)
# -------------------------------
cbc_explanations = {
    "LYMPHOCYTES": lambda data: f"""**Your lymphocyte count** is {data['status'].lower()} ({data['value']:.2f} {data.get('unit','')})
\nHigh lymphocytes commonly reflect an active immune response (viral infection, recovery, stress). Rest and hydration often help; consult your clinician if persistent.""",
    "MONOCYTES": lambda data: f"""**Your monocyte count** is {data['status'].lower()} ({data['value']:.2f} {data.get('unit','')})
\nMay indicate inflammation or recovery from infection. Anti-inflammatory diet, sleep, and follow-up testing are commonly recommended.""",
    "EOSINOPHILS": lambda data: f"""**Your eosinophil count** is {data['status'].lower()} ({data['value']:.2f} {data.get('unit','')})
\nOften related to allergies or parasitic causes. Consider allergy review or travel history review with your clinician.""",
    "BASOPHILS": lambda data: f"""**Your basophil count** is {data['status'].lower()} ({data['value']:.2f} {data.get('unit','')})
\nUncommon; may relate to allergic or inflammatory states — discuss with your provider for next steps.""",
    "HEMATOCRIT": lambda data: f"""**Your hematocrit** is {data['status'].lower()} ({data['value']:.2f} {data.get('unit','')})
\nHigh hematocrit often reflects dehydration, smoking, or conditions raising red cell mass. Hydration and clinician review recommended.""",
    "MCV": lambda data: f"""**Your MCV** is {data['status'].lower()} ({data['value']:.2f} {data.get('unit','')})
\nHigh MCV suggests larger red cells — commonly due to B12/folate deficiency, alcohol use, or meds. Nutritional evaluation often helps.""",
    "MCH": lambda data: f"""**Your MCH** is {data['status'].lower()} ({data['value']:.2f} {data.get('unit','')})
\nTends to mirror MCV results. Nutritional causes like B12/folate deficiency are common.""",
    "MCHC": lambda data: f"""**Your MCHC** is {data['status'].lower()} ({data['value']:.2f} {data.get('unit','')})
\nLess common; may require further testing if persistently abnormal.""",
    "RDW": lambda data: f"""**Your RDW** is {data['status'].lower()} ({data['value']:.2f} {data.get('unit','')})
\nIndicates variability in red cell size — think nutritional deficiencies or evolving anemia; follow-up tests often include iron/B12/folate.""",
    # Add more as needed...
}


# -------------------------------
# High/Low recommendations
# -------------------------------
def get_high_recommendations(param_key, data):
    """Return friendly, actionable guidance when a parameter is high."""
    param_key = param_key.upper()
    # If we've got a short explanation in dictionary, use it as a lead-in
    lead = cbc_explanations.get(param_key)
    lead_txt = lead(data) if callable(lead) else ""

    # Parameter-specific advice
    if param_key in ("LYMPHOCYTES", "MONOCYTES", "EOSINOPHILS", "BASOPHILS"):
        advice = (
            f"{lead_txt}\n\n**Common causes & suggestions:**\n"
            "- Often related to infection, allergy, inflammation, or recovery.\n"
            "- Rest, hydration, and treating any known infections/allergies usually help.\n"
            "- If levels remain high or you have concerning symptoms (fever, weight loss, night sweats), see your doctor.\n"
            "- Your clinician may repeat the test or order targeted tests (allergy testing, infection screen, inflammatory markers).\n"
        )
        return advice

    if param_key == "HEMATOCRIT":
        return (
            f"{lead_txt}\n\n**What to try:**\n"
            "- Drink more fluids; dehydration often raises hematocrit.\n"
            "- Avoid smoking; treat sleep apnea if present.\n"
            "- If persistent, your clinician may check oxygenation, kidney function, or consider referral to hematology.\n"
        )

    if param_key in ("MCV", "MCH"):
        return (
            f"{lead_txt}\n\n**Likely causes & next steps:**\n"
            "- Consider B12 or folate deficiency, alcohol use, or medication effects.\n"
            "- Nutritional review and blood tests for B12/folate/liver function are common next steps.\n"
            "- Supplements or dietary changes often help when deficiency is confirmed.\n"
        )

    if param_key == "MCHC":
        return (
            f"{lead_txt}\n\n**This finding is less common.**\n"
            "- It may relate to specific red cell conditions or lab variation.\n"
            "- Your clinician may repeat the test and consider further hematology workup.\n"
        )

    if param_key == "RDW":
        return (
            f"{lead_txt}\n\n**Interpretation & suggestions:**\n"
            "- RDW rising often means mixed cell sizes — look for nutrient deficiencies.\n"
            "- Tests for iron, B12, and folate are commonly ordered.\n            "
        )

    # Default fallback for other high parameters
    return (
        f"{lead_txt}\n\n**General advice for elevated values:**\n"
        "- Many elevated values are temporary (illness, dehydration, stress).\n"
        "- Stay hydrated, rest, and follow up with your clinician if it persists.\n"
        "- Bring this report to your appointment so your provider can interpret it in context.\n"
    )


def get_low_recommendations(param_key, data):
    """Return friendly, actionable guidance when a parameter is low."""
    param_key = param_key.upper()
    lead = cbc_explanations.get(param_key)
    lead_txt = lead(data) if callable(lead) else ""

    if param_key in ("HEMOGLOBIN", "RBC COUNT", "HEMATOCRIT"):
        return (
            f"{lead_txt}\n\n**Common causes & actions:**\n"
            "- Low values often reflect anemia caused by iron deficiency, chronic disease, or blood loss.\n"
            "- Dietary iron, B12, and folate intake are important; your clinician may order iron studies and ferritin.\n"
            "- If symptomatic (fatigue, breathlessness), seek medical advice promptly.\n"
        )

    if param_key in ("PLATELET COUNT",):
        return (
            f"{lead_txt}\n\n**Low platelets (thrombocytopenia) may be due to:**\n"
            "- Viral infections, some medications, or immune causes.\n"
            "- Avoid NSAIDs and blood thinners until reviewed if platelets are low.\n"
            "- Your clinician may repeat the test and investigate causes if platelets are significantly low.\n"
        )

    if param_key in ("NEUTROPHILS",):
        return (
            f"{lead_txt}\n\n**Low neutrophils (neutropenia) — important to monitor:**\n"
            "- May increase infection risk. Avoid contact with sick people and practice good hygiene.\n"
            "- Your clinician may repeat the test and review medications or bone marrow causes.\n"
        )

    if param_key in ("LYMPHOCYTES", "MONOCYTES", "EOSINOPHILS", "BASOPHILS"):
        return (
            f"{lead_txt}\n\n**Low levels:**\n"
            "- Can reflect recent illness, certain medications, or immune changes.\n"
            "- Often transient; if persistent, your clinician will investigate further.\n"
        )

    if param_key in ("MCV", "MCH", "MCHC", "RDW"):
        return (
            f"{lead_txt}\n\n**Low red cell indices:**\n"
            "- Often suggest iron deficiency or microcytic anemia.\n"
            "- Iron studies and dietary evaluation are usually recommended.\n"
        )

    # Default fallback
    return (
        f"{lead_txt}\n\n**General advice for lower-than-normal values:**\n"
        "- Many low values are manageable with nutrition, medication review, or treating underlying causes.\n"
        "- Consult your clinician for targeted tests and personalized treatment.\n"
    )


# -------------------------------
# Existing helpers (explanations/value retrieval/etc.)
# -------------------------------
def get_parameter_explanation(question_lower, assessment, param_variations):
    """Provide friendly explanations of parameters referenced in the question."""
    param_key, data = find_parameter_in_assessment(question_lower, assessment, param_variations)
    param_info = {
        "HEMOGLOBIN": {"name": "Hemoglobin", "simple": "the protein in red blood cells that carries oxygen"},
        "TOTAL LEUKOCYTE COUNT": {"name": "White Blood Cells (WBC)", "simple": "your immune system's defense team"},
        "RBC COUNT": {"name": "Red Blood Cells (RBC)", "simple": "cells that carry oxygen throughout your body"},
        "PLATELET COUNT": {"name": "Platelets", "simple": "help your blood clot"},
        "HEMATOCRIT": {"name": "Hematocrit", "simple": "the percentage of your blood made up of red blood cells"},
        "MCV": {"name": "MCV", "simple": "average size of your red blood cells"},
        "NEUTROPHILS": {"name": "Neutrophils", "simple": "white cells that fight bacterial infections"},
        "LYMPHOCYTES": {"name": "Lymphocytes", "simple": "white cells that fight viruses and support immunity"},
        "MONOCYTES": {"name": "Monocytes", "simple": "white cells that clean up debris and aid repair"},
        "EOSINOPHILS": {"name": "Eosinophils", "simple": "white cells involved in allergy and parasites"},
        "BASOPHILS": {"name": "Basophils", "simple": "involved in allergic responses"},
    }

    if param_key and param_key in param_info:
        info = param_info[param_key]
        response = f"**{info['name']}** — {info['simple']}.\n\n"
        if data:
            response += f"**Your value:** {data['value']:.2f} {data.get('unit', '')}\n"
            response += f"**Status:** {data.get('status', 'Unknown')}\n"
            if 'range' in data:
                response += f"**Normal range:** {data['range']}\n"
        return response
    return None


def get_parameter_value_response(question_lower, assessment, param_variations):
    """Return value and short guidance for requested parameter."""
    param_key, data = find_parameter_in_assessment(question_lower, assessment, param_variations)
    if param_key and data:
        status = data.get('status', 'Unknown')
        response = f"**{param_key}:** {data['value']:.2f} {data.get('unit', '')}\n\n"
        if status == 'Normal':
            response += "✅ **Status:** Within normal range — nothing specific needed.\n"
        elif status == 'High':
            response += "📈 **Status:** Elevated — consider follow-up and review causes.\n"
        elif status == 'Low':
            response += "📉 **Status:** Below reference — may need evaluation depending on symptoms.\n"
        if 'range' in data:
            response += f"\n**Normal range:** {data['range']}\n"
        response += "\nAsk me for 'what to do' if you'd like specific suggestions."
        return response

    # If not found, try to detect referenced param keywords and provide helpful message
    for keyword, assessment_key in param_variations.items():
        if keyword in question_lower:
            return f"I couldn't find {assessment_key} in this report. It may not be measured or the report hasn't been analyzed yet."
    return None


def get_high_low_advice(question_lower, assessment, param_variations):
    """Route to high/low recommendation helpers based on question intent."""
    param_key, data = find_parameter_in_assessment(question_lower, assessment, param_variations)
    if not param_key or not data:
        return None
    status = data.get('status', '')
    asking_high = any(word in question_lower for word in ["high", "elevated", "increase", "above"])
    asking_low = any(word in question_lower for word in ["low", "decrease", "reduced", "below"])
    # If user asked specifically about high/low
    if asking_high and status == "High":
        return get_high_recommendations(param_key, data)
    if asking_low and status == "Low":
        return get_low_recommendations(param_key, data)
    # If mismatch (user asked about high but value not high), reassure
    if asking_high and status != "High":
        return f"Good news — your {param_key} is not high. It's {status.lower()} ({data['value']:.2f} {data.get('unit','')})."
    if asking_low and status != "Low":
        return f"Good news — your {param_key} is not low. It's {status.lower()} ({data['value']:.2f} {data.get('unit','')})."
    # If general, provide specific guidance based on status
    if status == "High":
        return get_high_recommendations(param_key, data)
    if status == "Low":
        return get_low_recommendations(param_key, data)
    return None


def get_what_to_do_response(question_lower, assessment, param_variations):
    """Return practical advice when user asks what to do about a parameter."""
    param_key, data = find_parameter_in_assessment(question_lower, assessment, param_variations)
    if param_key and data:
        status = data.get('status', '')
        if status == "High":
            return get_high_recommendations(param_key, data)
        if status == "Low":
            return get_low_recommendations(param_key, data)
        return (f"**Your {param_key} is within the normal range** ({data['value']:.2f} {data.get('unit','')}).\n"
                "Maintain healthy habits: balanced diet, hydration, sleep, and exercise.")
    # If no specific parameter, return general plan
    return get_general_action_plan(assessment)


def get_reassurance_response(question_lower, assessment, param_variations):
    """Provide calming, reassuring response for worry-related queries."""
    param_key, data = find_parameter_in_assessment(question_lower, assessment, param_variations)
    if param_key and data:
        status = data.get('status', 'Unknown')
        if status == 'Normal':
            return f"✅ No need to worry — your {param_key} is within the normal range ({data['value']:.2f} {data.get('unit','')})."
        return (f"I understand concern — your {param_key} is {status.lower()} ({data['value']:.2f} {data.get('unit','')}). "
                "Many mild abnormalities are temporary. Please discuss with your healthcare provider for personalized advice.")
    # If asking about overall worry
    abnormal_count = sum(1 for d in assessment.get('assessed', {}).values() if d.get('status') in ['High', 'Low'])
    if abnormal_count == 0:
        return "Great news — no significant abnormalities detected in your CBC."
    return (f"I see {abnormal_count} parameter(s) outside reference ranges. Many causes are temporary; please follow up with your clinician for tailored guidance.")


def get_comparison_response(question_lower, assessment, param_variations):
    """Compare multiple parameters mentioned in the question."""
    mentioned = []
    for keyword, assessment_key in param_variations.items():
        if keyword in question_lower and assessment_key in assessment.get('assessed', {}):
            mentioned.append(assessment_key)
    if len(mentioned) < 2:
        return None
    response = "**Comparison of mentioned parameters:**\n"
    for param in mentioned[:5]:
        d = assessment['assessed'].get(param, {})
        response += f"- {param}: {d.get('value','N/A')} {d.get('unit','')} — {d.get('status','Unknown')}\n"
    response += "\nNote: each parameter conveys different information; review with your clinician for full context."
    return response


def get_cbc_general_info(question_lower, assessment):
    """Return generic CBC information."""
    return ("**Complete Blood Count (CBC)** — a standard test measuring red cells, white cells, and platelets.\n\n"
            "Ask about any specific parameter for tailored info (e.g., 'What is hemoglobin?').")


def get_general_action_plan(assessment):
    """Overall action plan based on whether there are abnormalities."""
    abnormalities = [(p, d.get('status')) for p, d in assessment.get('assessed', {}).items() if d.get('status') in ['High', 'Low']]
    if not abnormalities:
        return ("Your CBC looks good overall. Maintain balanced diet, hydration, activity, and routine follow-up with your healthcare provider.")
    response = "**Action plan:**\n"
    for param, status in abnormalities[:5]:
        response += f"- {param}: {status}\n"
    response += ("\nSchedule a follow-up with your clinician to interpret these in your full medical context. "
                 "Bring this report and any symptoms you're experiencing.")
    return response


def get_smart_guidance_response(question_lower, assessment, cbc_data, param_variations):
    """Fallback: attempt to infer user's intent and suggest next steps or values."""
    # Try to find a param match
    for keyword, param_key in param_variations.items():
        if keyword in question_lower and param_key in assessment.get('assessed', {}):
            data = assessment['assessed'][param_key]
            return (f"**{param_key}:** {data.get('value','N/A')} {data.get('unit','')} — {data.get('status','Unknown')}\n"
                    f"Ask: 'What does this mean?', 'What should I do?', or 'What's the normal range?'")
    # If nothing specific, show abnormal parameters if any
    abnormal = [p for p, d in assessment.get('assessed', {}).items() if d.get('status') in ['High', 'Low']]
    if abnormal:
        return ("I see some values outside reference ranges. Try asking:\n"
                f"- 'Give me a summary'\n- 'What should I do about my {abnormal[0].lower()}?'\n")
    return ("I can explain parameters, give normal ranges, or summarize your report. Try: 'What is hemoglobin?' or 'Give me a summary.'")


def get_clean_report_summary(assessment, cbc_data):
    """Produce a friendly summary of the provided CBC assessment and cbc_data metadata."""
    if not assessment or 'assessed' not in assessment:
        return "No report data available. Upload and analyze a CBC first."
    normal = []
    abnormal = []
    for p, d in assessment['assessed'].items():
        if d.get('value') is None:
            continue
        status = d.get('status', 'Unknown')
        entry = f"{p}: {d['value']:.2f} {d.get('unit','')}"
        if status == 'Normal':
            normal.append(entry)
        else:
            abnormal.append(f"{entry} ({status})")
    age = cbc_data.get('Age', 'N/A') if cbc_data else 'N/A'
    sex = cbc_data.get('Sex', 'N/A') if cbc_data else 'N/A'
    response = f"**CBC Summary**\nPatient: Age {age}, {sex}\n\n"
    response += f"Analyzed parameters: {len(normal) + len(abnormal)}\n"
    response += f"Normal: {len(normal)}\nOutside range: {len(abnormal)}\n\n"
    if abnormal:
        response += "**Parameters needing attention:**\n"
        for a in abnormal:
            response += f"- {a}\n"
        response += "\nPlease review these with your clinician."
    else:
        response += "All values fall within reference ranges. Great job!"
    return response


def get_clean_normal_ranges():
    """Return a short listing of typical CBC normal ranges."""
    return (
        "**CBC Normal Ranges (typical)**\n\n"
        "Hemoglobin: Men 13.5-17.5 g/dL | Women 12.0-15.5 g/dL\n"
        "Hematocrit: Men 41-50% | Women 36-44%\n"
        "RBC: Men 4.7-6.1M/μL | Women 4.2-5.4M/μL\n"
        "WBC: 4.5-11.0 K/μL\n"
        "Neutrophils: 40-60% | Lymphocytes: 20-40% | Monocytes: 2-8%\n"
        "Eosinophils: 1-4% | Basophils: 0.5-1%\n"
        "Platelets: 150k-450k/μL\n\n"
        "Ranges vary by lab and patient. Ask about a specific parameter for details."
    )


# Routes
@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')


@app.route('/chat')
def chat():
    """Chat interface"""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        session['username'] = f"User_{session['user_id'][:8]}"
    
    return render_template('chat.html', username=session.get('username'))


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and OCR"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save file
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Extract text
    extracted_text, error = extract_text_from_file(filepath)
    
    if error:
        return jsonify({'error': f'OCR failed: {error}'}), 500
    
    # Store in session
    session['raw_text'] = extracted_text
    session['filepath'] = filepath
    
    return jsonify({
        'success': True,
        'text': extracted_text[:500] + '...' if len(extracted_text) > 500 else extracted_text
    })


@app.route('/upload_text', methods=['POST'])
def upload_text():
    """Handle manual text input"""
    data = request.json
    text = data.get('text', '')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    session['raw_text'] = text
    
    return jsonify({'success': True})


@app.route('/analyze', methods=['POST'])
def analyze():
    """Analyze CBC report"""
    if 'raw_text' not in session:
        return jsonify({'error': 'No report data found. Please upload a report first.'}), 400
    
    raw_text = session['raw_text']
    
    # DEBUG: Print raw text (first 500 characters)
    print("=== RAW TEXT (first 500 chars) ===")
    print(raw_text[:500])
    print("==================================")
    
    # Extract CBC data
    cbc_data = extract_cbc_clean(raw_text)
    
    # DEBUG: Print extracted CBC data
    print("=== EXTRACTED CBC DATA ===")
    print(f"Age: {cbc_data.get('Age')}")
    print(f"Sex: {cbc_data.get('Sex')}")
    print("Parameters:")
    for param, value in cbc_data.get('Parameters', {}).items():
        if value is not None:
            print(f"  {param}: {value}")
    print("Raw Parameters:")
    for param, raw_data in cbc_data.get('Raw_Parameters', {}).items():
        if raw_data.get('raw'):
            print(f"  {param}: {raw_data.get('raw')} {raw_data.get('unit')}")
    print("===========================")

    # Get age and sex from request or extracted data
    data = request.json or {}
    age = data.get('age') or cbc_data.get('Age')
    sex = data.get('sex') or cbc_data.get('Sex')
    
    # Assess CBC
    assessment = assess_cbc(cbc_data['Parameters'], age=age, sex=sex)
    
    # Store in session
    session['cbc_data'] = cbc_data
    session['assessment'] = assessment
    session['age'] = age
    session['sex'] = sex
    
    # Save to database
    user_id = db.create_user(session.get('username'))
    session['user_id'] = user_id
    
    report_id = db.save_report(
        user_id,
        age,
        sex,
        raw_text,
        cbc_data['Parameters'],
        assessment
    )
    session['report_id'] = report_id
    
    # Prepare response
    results = []
    for param, data in assessment['assessed'].items():
        if data['value'] is not None:
            results.append({
                'parameter': param,
                'value': round(data['value'], 2),
                'unit': data['unit'],
                'status': data['status'],
                'range': data.get('range', 'N/A')
            })
    
    return jsonify({
        'success': True,
        'age': age,
        'sex': sex,
        'results': results,
        'report_id': report_id
    })


@app.route('/ask', methods=['POST'])
def ask_question():
    """Handle chat questions"""
    if 'cbc_data' not in session or 'assessment' not in session:
        return jsonify({
            'error': 'Please analyze a report first before asking questions.'
        }), 400
    
    data = request.json
    question = data.get('question', '')
    
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    
    # Generate response
    cbc_data = session['cbc_data']
    assessment = session['assessment']
    
    response = generate_ai_response(question, cbc_data, assessment)
    
    # Save to database
    if 'user_id' in session and 'report_id' in session:
        db.save_chat(
            session['user_id'],
            session['report_id'],
            question,
            response
        )
    
    return jsonify({
        'success': True,
        'response': response
    })


@app.route('/history')
def get_history():
    """Get user's report history"""
    if 'user_id' not in session:
        return jsonify({'reports': []})
    
    reports = db.get_user_reports(session['user_id'])
    
    # Format for display
    formatted_reports = []
    for report in reports:
        # Count abnormal parameters
        abnormal_count = 0
        for param, data in report['assessment']['assessed'].items():
            if data['status'] in ['Low', 'High']:
                abnormal_count += 1
        
        formatted_reports.append({
            'report_id': report['report_id'],
            'date': report['date'],
            'age': report['age'],
            'sex': report['sex'],
            'abnormal_count': abnormal_count
        })
    
    return jsonify({'reports': formatted_reports})


@app.route('/trends')
def get_trends():
    """Get parameter trends over time"""
    if 'user_id' not in session:
        return jsonify({'trends': {}})
    
    reports = db.get_user_reports(session['user_id'], limit=10)
    
    if len(reports) < 2:
        return jsonify({'message': 'Need at least 2 reports to show trends'})
    
    # Extract trends for key parameters
    trends = {}
    key_params = ['HEMOGLOBIN', 'TOTAL LEUKOCYTE COUNT', 'PLATELET COUNT']
    
    for param in key_params:
        trends[param] = []
        for report in reversed(reports):
            param_data = report['assessment']['assessed'].get(param)
            if param_data:
                trends[param].append({
                    'date': report['date'],
                    'value': param_data['value'],
                    'status': param_data['status']
                })
    
    return jsonify({'trends': trends})


@app.route('/summary')
def get_summary():
    """Get current report summary"""
    if 'assessment' not in session:
        return jsonify({'error': 'No report analyzed yet'}), 400
    
    assessment = session['assessment']
    
    normal_count = 0
    low_count = 0
    high_count = 0
    abnormal_params = []
    
    for param, data in assessment['assessed'].items():
        status = data['status']
        if status == 'Normal':
            normal_count += 1
        elif status == 'Low':
            low_count += 1
            abnormal_params.append({
                'parameter': param,
                'value': data['value'],
                'unit': data['unit'],
                'status': 'Low'
            })
        elif status == 'High':
            high_count += 1
            abnormal_params.append({
                'parameter': param,
                'value': data['value'],
                'unit': data['unit'],
                'status': 'High'
            })
    
    return jsonify({
        'normal_count': normal_count,
        'low_count': low_count,
        'high_count': high_count,
        'abnormal_params': abnormal_params,
        'age': session.get('age'),
        'sex': session.get('sex')
    })


@app.route('/clear_session', methods=['POST'])
def clear_session():
    """Clear current session"""
    session.clear()
    return jsonify({'success': True})

@app.route('/get_analyzer_data', methods=['GET'])
def get_analyzer_data():
    """Get detailed analyzer data with dataframe"""
    if 'cbc_data' not in session or 'assessment' not in session:
        return jsonify({'error': 'No report analyzed yet. Please upload and analyze a CBC report first.'}), 400
    
    try:
        cbc_data = session['cbc_data']
        assessment = session['assessment']
        
        # DEBUG: Print what's actually in cbc_data
        print("=== DEBUG: CBC DATA STRUCTURE ===")
        print(f"Age: {cbc_data.get('Age')}")
        print(f"Sex: {cbc_data.get('Sex')}")
        print("Parameters found:")
        if 'Parameters' in cbc_data and cbc_data['Parameters']:
            for param, value in cbc_data['Parameters'].items():
                print(f"  - {param}: {value}")
        else:
            print("  No parameters found or 'Parameters' key is empty!")
        
        print("Raw Parameters:")
        if 'Raw_Parameters' in cbc_data and cbc_data['Raw_Parameters']:
            for param, raw_data in cbc_data['Raw_Parameters'].items():
                print(f"  - {param}: {raw_data}")
        else:
            print("  No raw parameters found!")
        print("==================================")
        
        # Unit scaling
        unit_scaling = {
            "10*3": 1e-3,
            "10*6": 1e-6,
            "%": 1,
            "g/dL": 1, "g/dl": 1,
            "fL": 1,
            "pg": 1,
            "mm/hr": 1
        }
        
        # Create dataframe
        df_list = []
        for k, v in cbc_data["Parameters"].items():
            if v is not None:
                raw_unit = cbc_data["Raw_Parameters"][k]["unit"]
                ref_range = cbc_data["Ranges"].get(k)
                df_list.append({
                    "Parameter": k,
                    "Value": round(v * unit_scaling.get(raw_unit, 1), 2),
                    "Unit": raw_unit,
                    "Reference Low": ref_range[0] if ref_range else None,
                    "Reference High": ref_range[1] if ref_range else None
                })
        
        # Add assessed values
        for item in df_list:
            param = item['Parameter']
            if param in assessment['assessed']:
                item['Status'] = assessment['assessed'][param]['status']
        
        # Add absolute counts
        absolute_counts = []
        for key, val in assessment['absolute_counts'].items():
            absolute_counts.append({
                "Parameter": key,
                "Value": round(val['value'], 2),
                "Unit": val['unit'],
                "Reference Low": None,
                "Reference High": None,
                "Status": None
            })
        
        # DEBUG: Print what's being sent to frontend
        print("=== DEBUG: Sending to Frontend ===")
        print(f"Parameters count: {len(df_list)}")
        for item in df_list:
            print(f"  - {item['Parameter']}: {item['Value']} {item['Unit']} (Status: {item.get('Status', 'N/A')})")
        print(f"Absolute counts: {len(absolute_counts)}")
        for item in absolute_counts:
            print(f"  - {item['Parameter']}: {item['Value']} {item['Unit']}")
        print("==================================")
        
        return jsonify({
            'success': True,
            'parameters': df_list,
            'absolute_counts': absolute_counts
        })
        
    except Exception as e:
        print(f"Error in get_analyzer_data: {e}")
        return jsonify({'error': f'Error processing analyzer data: {str(e)}'}), 500
    
@app.route('/update_parameter', methods=['POST'])
def update_parameter():
    """Update a specific parameter value"""
    if 'cbc_data' not in session or 'assessment' not in session:
        return jsonify({'error': 'No report analyzed yet'}), 400
    
    data = request.json
    parameter = data.get('parameter')
    new_value = data.get('value')
    
    if not parameter or new_value is None:
        return jsonify({'error': 'Invalid data'}), 400
    
    # Update in session
    cbc_data = session['cbc_data']
    assessment = session['assessment']
    
    if parameter in cbc_data['Parameters']:
        cbc_data['Parameters'][parameter] = float(new_value)
        
        # Re-assess
        age = session.get('age')
        sex = session.get('sex')
        assessment = assess_cbc(cbc_data['Parameters'], age=age, sex=sex)
        
        session['cbc_data'] = cbc_data
        session['assessment'] = assessment
        
        return jsonify({'success': True})
    
    return jsonify({'error': 'Parameter not found'}), 404


@app.route('/get_correlations', methods=['GET'])
def get_correlations():
    """Get clinical correlations"""
    if 'assessment' not in session:
        return jsonify({'error': 'No report analyzed yet. Please upload and analyze a CBC report first.'}), 400
    
    try:
        assessment = session['assessment']
        
        correlations = set()
        assessed_dict = assessment['assessed']
        
        # Anemia / RBC issues
        hgb_status = assessed_dict.get("HEMOGLOBIN", {}).get("status")
        hct_status = assessed_dict.get("HEMATOCRIT", {}).get("status")
        
        if hgb_status == "Low" or hct_status == "Low":
            mcv_status = assessed_dict.get("MCV", {}).get("status")
            if mcv_status == "Low":
                correlations.add("Microcytic anemia (possible iron deficiency).")
            elif mcv_status == "High":
                correlations.add("Macrocytic anemia (possible B12/Folate deficiency).")
            else:
                correlations.add("Normocytic anemia (possible chronic disease).")
        
        # WBC / Infection
        wbc_status = assessed_dict.get("TOTAL LEUKOCYTE COUNT", {}).get("status")
        if wbc_status == "Low":
            correlations.add("Leukopenia (possible bone marrow suppression or viral infection).")
        elif wbc_status == "High":
            neut_status = assessed_dict.get("NEUTROPHILS", {}).get("status")
            lymph_status = assessed_dict.get("LYMPHOCYTES", {}).get("status")
            if neut_status == "High":
                correlations.add("Suggestive of bacterial infection.")
            elif lymph_status == "High":
                correlations.add("Suggestive of viral infection.")
        
        # Platelets
        plt_status = assessed_dict.get("PLATELET COUNT", {}).get("status")
        if plt_status == "Low":
            correlations.add("Thrombocytopenia (risk of bleeding disorders).")
        elif plt_status == "High":
            correlations.add("Thrombocytosis (possible inflammation or myeloproliferative disorder).")
        
        # Differential counts
        for diff in ["NEUTROPHILS", "LYMPHOCYTES", "MONOCYTES", "EOSINOPHILS", "BASOPHILS"]:
            status = assessed_dict.get(diff, {}).get("status")
            if status == "High":
                correlations.add(f"High {diff} count.")
            elif status == "Low":
                correlations.add(f"Low {diff} count.")
        
        # ESR
        esr_status = assessed_dict.get("ESR", {}).get("status")
        if esr_status == "High":
            correlations.add("Elevated ESR indicates inflammation or chronic disease.")
        
        return jsonify({
            'success': True,
            'correlations': list(correlations)
        })
        
    except Exception as e:
        print(f"Error in get_correlations: {e}")
        return jsonify({'error': f'Error processing correlations: {str(e)}'}), 500

@app.route('/get_all_trends', methods=['GET'])
def get_all_trends():
    """Get trends for all parameters (last 4 reports)"""
    if 'user_id' not in session:
        return jsonify({'message': 'Please log in to view trends'})
    
    try:
        reports = db.get_user_reports(session['user_id'], limit=4)
        
        if len(reports) == 0:
            return jsonify({'message': 'No historical reports found. Analyze at least one report to see trends.'})
        
        # Extract all parameters from all reports
        all_params = set()
        for report in reports:
            if 'parameters' in report and report['parameters']:
                for param in report['parameters'].keys():
                    if report['parameters'][param] is not None:
                        all_params.add(param)
        
        trends = {}
        for param in all_params:
            trends[param] = []
            for report in reports:
                if ('assessment' in report and 
                    'assessed' in report['assessment'] and 
                    param in report['assessment']['assessed']):
                    
                    param_data = report['assessment']['assessed'][param]
                    if param_data and param_data.get('value') is not None:
                        trends[param].append({
                            'date': report['date'],
                            'value': param_data['value'],
                            'status': param_data.get('status', 'Unknown'),
                            'unit': param_data.get('unit', 'N/A')
                        })
        
        # Remove empty trends
        trends = {k: v for k, v in trends.items() if v}
        
        if not trends:
            return jsonify({'message': 'No trend data available from historical reports'})
        
        return jsonify({'trends': trends})
        
    except Exception as e:
        print(f"Error in get_all_trends: {e}")
        return jsonify({'error': f'Error processing trends: {str(e)}'}), 500


@app.route('/clear_history', methods=['POST'])
def clear_history():
    """Clear user history"""
    if 'user_id' not in session:
        return jsonify({'error': 'No user found'}), 400
    
    try:
        # Delete from database
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        user_id = session['user_id']
        
        # Delete chat history
        cursor.execute('DELETE FROM chat_history WHERE user_id = ?', (user_id,))
        
        # Delete reports
        cursor.execute('DELETE FROM reports WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        
        # Clear session
        session.clear()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download_full_report', methods=['GET'])
def download_full_report():
    """Download complete report as PDF"""
    if 'assessment' not in session or 'cbc_data' not in session:
        return jsonify({'error': 'No report to download'}), 400
    
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from io import BytesIO
        from datetime import datetime
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0d47a1'),
            spaceAfter=30,
            alignment=1  # Center
        )
        elements.append(Paragraph("CBC Lab Report Analysis", title_style))
        elements.append(Spacer(1, 0.3*inch))
        
        # Patient Info
        patient_data = session.get('patient_data', {})
        info_text = f"""
        <b>Patient Information</b><br/>
        Name: {patient_data.get('name', 'N/A')}<br/>
        Age: {session.get('age', 'N/A')}<br/>
        Sex: {session.get('sex', 'N/A')}<br/>
        Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        elements.append(Paragraph(info_text, styles['Normal']))
        elements.append(Spacer(1, 0.5*inch))
        
        # Results Table
        assessment = session['assessment']
        table_data = [['Parameter', 'Value', 'Unit', 'Status', 'Reference Range']]
        
        for param, data in assessment['assessed'].items():
            if data['value'] is not None:
                table_data.append([
                    param,
                    f"{data['value']:.2f}",
                    data['unit'],
                    data['status'],
                    data.get('range', 'N/A')
                ])
        
        table = Table(table_data, colWidths=[2.5*inch, 1*inch, 0.8*inch, 1*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        
        elements.append(Paragraph("<b>CBC Parameters</b>", styles['Heading2']))
        elements.append(Spacer(1, 0.2*inch))
        elements.append(table)
        
        # Disclaimer
        elements.append(Spacer(1, 0.5*inch))
        disclaimer = """
        <b>DISCLAIMER:</b> This report is for informational purposes only and should not be used 
        as a substitute for professional medical advice, diagnosis, or treatment. Always consult 
        your healthcare provider regarding any medical condition.
        """
        elements.append(Paragraph(disclaimer, styles['Normal']))
        
        doc.build(elements)
        buffer.seek(0)
        
        return buffer.getvalue(), 200, {
            'Content-Type': 'application/pdf',
            'Content-Disposition': f'attachment; filename=CBC_Report_{datetime.now().strftime("%Y%m%d")}.pdf'
        }
        
    except ImportError:
        return jsonify({'error': 'ReportLab not installed. Install with: pip install reportlab'}), 500
    except Exception as e:
        return jsonify({'error': f'Error generating PDF: {str(e)}'}), 500


@app.route('/get_visualization_data', methods=['GET'])
def get_visualization_data():
    """Get data for visualization charts"""
    if 'assessment' not in session:
        return jsonify({'error': 'No report analyzed yet. Please upload and analyze a CBC report first.'}), 400
    
    try:
        assessment = session['assessment']
        
        # Prepare data for charts
        chart_data = {
            'parameters': [],
            'values': [],
            'statuses': [],
            'units': []
        }
        
        for param, data in assessment['assessed'].items():
            if data['value'] is not None:
                chart_data['parameters'].append(param)
                chart_data['values'].append(round(data['value'], 2))
                chart_data['statuses'].append(data['status'])
                chart_data['units'].append(data['unit'])
        
        return jsonify({
            'success': True,
            'chart_data': chart_data
        })
        
    except Exception as e:
        print(f"Error in get_visualization_data: {e}")
        return jsonify({'error': f'Error processing visualization data: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)