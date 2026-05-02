"""
Planner Module - Intent Classification for CRM AI Bot
"""

def decide(text: str) -> str:
    """Determine user intent and map to appropriate action"""
    
    if not text or not text.strip():
        return "llm_response"
    
    text = text.lower().strip()
    
    # Normalize text
    text = text.replace("-", " ").replace("_", " ")
    text = " ".join(text.split())
    text = text.replace("regitration", "registration")
    text = text.replace("rgistration", "registration")
    text = text.replace("registeration", "registration")
    text = text.replace("stsutus", "status")
    text = text.replace("ststus", "status")
    text = text.replace("lead status", "lead status")

    conversation_phrases = [
        "help", "commands", "hi", "hello", "hey", "start",
        "what can you do", "how can you help", "how can you help me",
        "what do you do", "who are you", "about you", "explain",
        "how to use", "how do i use", "examples", "sample questions",
        "what should i ask", "why use this bot", "what is this bot",
    ]
    if text in conversation_phrases or any(phrase in text for phrase in conversation_phrases):
        return "llm_response"
    
    # Document requests (highest priority)
    document_services = [
        "gst", "msme", "iso", "fssai", "iec", "bee", "bis", "isi",
        "plastic", "battery", "ewaste", "e waste", "cdsco", "lmpc",
        "pims", "tec", "wpc", "steel", "oil", "epr", "company registration"
    ]

    doc_triggers = ["document", "documents", "docs", "requirement", "paperwork", 
                    "checklist", "what do i need", "required for", "registration",
                    "epr registration", "return"]
    if any(trigger in text for trigger in doc_triggers):
        if any(service in text for service in document_services):
            return "service_documents"
    
    # Specific document service detection
    if any(service in text for service in document_services):
        if any(word in text for word in ["doc", "require", "need", "list", "registration", "return"]):
            return "service_documents"

    if text in document_services:
        return "service_documents"
    
    # Payment history
    if "payment" in text and any(word in text for word in ["history", "record", "past"]):
        return "payment_history"
    
    # Pending payments
    if any(word in text for word in ["pending payment", "due payment", "outstanding"]):
        return "pending_payment"
    
    # Status report
    if any(word in text for word in ["status", "report", "summary", "statistics", "total"]):
        if "lead" in text or "overall" in text:
            return "status_report"
    
    # Search customer
    search_triggers = ["search", "find", "lookup"]
    customer_triggers = ["customer", "client"]
    contact_triggers = ["email", "mobile", "phone", "contact"]
    
    if any(word in text for word in search_triggers + customer_triggers + contact_triggers):
        return "customer_search"
    
    # Lead details
    if any(word in text for word in ["lead details", "company details", "show lead", "get lead"]):
        return "lead_details"
    
    if "lead" in text and any(word in text for word in ["detail", "details", "info", "information"]):
        return "lead_details"
    
    # Today's leads
    if "today" in text and "lead" in text:
        return "today_leads"
    
    # Simple lead queries
    if text in ["leads", "all leads", "show leads", "get leads", "list leads", "all lead", "show all leads"]:
        return "all_leads"
    
    # Fallback: treat normal text as a lead/company name lookup.
    return "lead_details"
