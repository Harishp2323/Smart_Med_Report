# CBC_Chat_Assistant
CBC Chat Assistant — an AI-assisted Complete Blood Count (CBC) report analyzer and chat assistant.
Upload a scanned CBC/PDF or paste text, and the app extracts CBC parameters (HGB, WBC, RBC, Platelets, MCV, MCH, MCHC, RDW, etc.), compares them to age/sex-specific reference ranges, provides human-friendly rule-based explanations, visualizations, and a conversational interface to ask about individual parameters.

# Folder creation

<pre>
  cbc_chatbot/
├── app.py
├── requirements.txt
├── models/
│   ├── __init__.py
│   ├── cbc_parser.py
│   └── database.py
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── chat.js
└── templates/
    ├── index.html
    └── chat.html
</pre>



