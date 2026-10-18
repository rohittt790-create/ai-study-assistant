import json
import math
import os
import re
import requests
from typing import List, Dict, Any, Tuple, Optional
from pdf_service import split_into_chunks

DEFAULT_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", 
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", 
    "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", 
    "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", 
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", 
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", 
    "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", 
    "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", 
    "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", 
    "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", 
    "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", 
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", 
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", 
    "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", 
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", 
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours"
}

def tokenize(text: str) -> List[str]:
    words = re.findall(r'\b[a-zA-Z0-9_\-]{2,}\b', text.lower())
    return [w for w in words if w not in STOPWORDS]

class TFIDFRetriever:
    def __init__(self, chunks: List[Dict[str, Any]]):
        self.chunks = chunks
        self.doc_count = len(chunks)
        self.df = {}
        self.chunk_tokens = []
        
        for c in chunks:
            tokens = set(tokenize(c["text"]))
            self.chunk_tokens.append(tokens)
            for token in tokens:
                self.df[token] = self.df.get(token, 0) + 1
                
    def search(self, query: str, top_k: int = 4) -> List[Tuple[Dict[str, Any], float]]:
        query_tokens = tokenize(query)
        if not query_tokens or self.doc_count == 0:
            return []
            
        scores = []
        for i, chunk in enumerate(self.chunks):
            tokens = self.chunk_tokens[i]
            score = 0.0
            matched_words = 0
            for qt in query_tokens:
                if qt in tokens:
                    matched_words += 1
                    # TF-IDF calculation
                    idf = math.log((self.doc_count + 1) / (self.df.get(qt, 1) + 1)) + 1
                    score += idf
                    
            # Boost score if multiple query terms match
            if matched_words > 1:
                score *= (1.0 + (matched_words / len(query_tokens)) * 0.5)
                
            scores.append((chunk, score))
            
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

# ==========================================
# BUILT-IN NLP SUMMARIZATION & EXTRACTION
# ==========================================

def extract_key_sentences(text: str, max_sentences: int = 5) -> List[str]:
    raw_sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 25 and len(s.strip().split()) > 4]
    if not sentences:
        return []
        
    all_tokens = tokenize(text)
    word_freq = {}
    for w in all_tokens:
        word_freq[w] = word_freq.get(w, 0) + 1
        
    ranked = []
    for s in sentences:
        s_tokens = tokenize(s)
        if not s_tokens:
            continue
        # Score by term frequency & bonus for defining keywords
        score = sum(word_freq.get(w, 0) for w in s_tokens) / (len(s_tokens) ** 0.5)
        lower_s = s.lower()
        if any(marker in lower_s for marker in ["is defined as", "refers to", "means", "crucial", "essential", "primary", "therefore", "results in", "key", "function of"]):
            score *= 1.4
        ranked.append((s, score))
        
    ranked.sort(key=lambda x: x[1], reverse=True)
    selected = [r[0] for r in ranked[:max_sentences]]
    # Return in original order of appearance
    return [s for s in sentences if s in selected]

def extract_definitions(pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    definitions = []
    seen_terms = set()
    
    definition_patterns = [
        r'\b([A-Z][a-zA-Z\s]{2,25})\s+(?:is defined as|refers to|is the process of|is a|means|can be described as)\s+([^.!?\n]+[.!?])',
        r'^\s*[\*\-]?\s*([A-Z][a-zA-Z0-9\s\-]{2,30}):\s*([^.!?\n]+[.!?])',
        r'\b([A-Z][a-zA-Z0-9\s\-]{2,25})\s*–\s*([^.!?\n]+[.!?])',
    ]
    
    for page in pages_data:
        text = page["text"]
        page_num = page["page"]
        
        for pat in definition_patterns:
            matches = re.findall(pat, text, re.MULTILINE)
            for term, explanation in matches:
                clean_term = term.strip().strip("-*•")
                clean_exp = explanation.strip()
                if len(clean_term) > 2 and len(clean_term) < 40 and clean_term.lower() not in seen_terms:
                    seen_terms.add(clean_term.lower())
                    definitions.append({
                        "term": clean_term,
                        "definition": clean_exp,
                        "page": page_num
                    })
                    
    return definitions[:12]

def generate_local_summary(pages_data: List[Dict[str, Any]], length: str = "medium", format_style: str = "standard") -> str:
    total_text = "\n\n".join([p["text"] for p in pages_data if p["text"]])
    if not total_text.strip():
        return "⚠️ The document contains no readable text to summarize."
        
    definitions = extract_definitions(pages_data)
    
    if length == "short":
        key_points = extract_key_sentences(total_text, max_sentences=4)
        out = "### 📌 Quick Executive Summary\n\n"
        out += "> **Overview**: This study material spans " + str(len(pages_data)) + " page(s). Here are the primary concepts and takeaways:\n\n"
        for i, pt in enumerate(key_points, 1):
            out += f"- **Takeaway {i}**: {pt}\n"
            
        if definitions:
            out += "\n#### 🔑 Essential Terms\n"
            for d in definitions[:3]:
                out += f"- **{d['term']}** *(Page {d['page']})*: {d['definition']}\n"
        return out
        
    elif length == "detailed":
        out = "### 📚 Comprehensive Study & Revision Guide\n\n"
        out += f"**Document Extent**: {len(pages_data)} pages | **Estimated Reading Time**: {max(1, len(total_text.split()) // 200)} mins\n\n"
        
        out += "#### 📑 Chapter & Page Breakdown\n\n"
        for page in pages_data:
            p_text = page["text"]
            if not p_text.strip():
                continue
            key_sents = extract_key_sentences(p_text, max_sentences=2)
            out += f"##### 📖 Page {page['page']} Highlights\n"
            if key_sents:
                for s in key_sents:
                    out += f"- {s}\n"
            else:
                out += f"- *Content covered on page {page['page']} (approx {page['word_count']} words).*\n"
            out += "\n"
            
        if definitions:
            out += "#### 🧠 Key Concepts & Glossary\n\n"
            for d in definitions:
                out += f"- **{d['term']}** *(Page {d['page']})*: {d['definition']}\n"
                
        out += "\n#### 🎯 Exam Preparation & Quick Review\n"
        general_sentences = extract_key_sentences(total_text, max_sentences=6)
        for s in general_sentences:
            out += f"- 💡 {s}\n"
            
        return out
        
    else: # medium
        if format_style == "bullets":
            key_points = extract_key_sentences(total_text, max_sentences=8)
            out = "### 📝 Key Revision Points (Bullet Summary)\n\n"
            for pt in key_points:
                out += f"- {pt}\n\n"
            return out
            
        key_points = extract_key_sentences(total_text, max_sentences=5)
        out = "### 📖 Core Study Summary\n\n"
        out += "Here is the structured synthesis of your study notes:\n\n"
        out += "#### 💡 Central Themes\n"
        for pt in key_points:
            out += f"- {pt}\n"
            
        if definitions:
            out += "\n#### 🔑 Critical Definitions\n"
            for d in definitions[:6]:
                out += f"- **{d['term']}** *(Page {d['page']})*: {d['definition']}\n"
                
        out += "\n#### 📌 Actionable Takeaways\n"
        out += f"- Review the key terms above before quizzes.\n"
        out += f"- Material is distributed across {len(pages_data)} pages with high information density.\n"
        return out

# ==========================================
# BUILT-IN QUIZ & FLASHCARD GENERATOR
# ==========================================

def generate_local_quiz(pages_data: List[Dict[str, Any]], count: int = 5) -> List[Dict[str, Any]]:
    definitions = extract_definitions(pages_data)
    total_text = "\n\n".join([p["text"] for p in pages_data if p["text"]])
    sentences = extract_key_sentences(total_text, max_sentences=count * 3)
    
    questions = []
    
    # 1. Generate from definitions
    for d in definitions:
        if len(questions) >= count:
            break
        term = d["term"]
        defin = d["definition"]
        other_terms = [other["term"] for other in definitions if other["term"] != term]
        
        # Build distractors
        distractors = other_terms[:3]
        while len(distractors) < 3:
            distractors.append(f"Alternative Theory {len(distractors) + 1}")
            
        options = [term] + distractors
        # Deterministic shuffle
        options.sort(key=lambda x: len(x))
        
        correct_idx = options.index(term)
        option_letters = ["A", "B", "C", "D"]
        
        questions.append({
            "id": len(questions) + 1,
            "question": f"Which concept or term matches this description: \"{defin}\"?",
            "options": options,
            "answer": option_letters[correct_idx],
            "explanation": f"On Page {d['page']}, '{term}' is defined as: {defin}",
            "page": d["page"]
        })
        
    # 2. Generate from key sentences if more needed
    for s in sentences:
        if len(questions) >= count:
            break
            
        words = [w for w in tokenize(s) if len(w) > 4]
        if not words:
            continue
        keyword = words[0].capitalize()
        masked_sentence = re.sub(re.escape(keyword), "_______", s, flags=re.IGNORECASE)
        
        distractor_pool = ["Static", "Dynamic", "Secondary", "Synthetic", "Standard", "Optimal"]
        distractors = [d for d in distractor_pool if d.lower() != keyword.lower()][:3]
        
        options = [keyword] + distractors
        options.sort()
        correct_idx = options.index(keyword)
        option_letters = ["A", "B", "C", "D"]
        
        # Find page
        page_num = 1
        for p in pages_data:
            if s in p["text"]:
                page_num = p["page"]
                break
                
        questions.append({
            "id": len(questions) + 1,
            "question": f"Complete the statement from your notes: \"{masked_sentence}\"",
            "options": options,
            "answer": option_letters[correct_idx],
            "explanation": f"According to Page {page_num}: \"{s}\"",
            "page": page_num
        })
        
    return questions[:count]

def generate_local_flashcards(pages_data: List[Dict[str, Any]], count: int = 8) -> List[Dict[str, Any]]:
    definitions = extract_definitions(pages_data)
    flashcards = []
    
    for i, d in enumerate(definitions):
        flashcards.append({
            "id": i + 1,
            "front": d["term"],
            "back": d["definition"],
            "page": d["page"]
        })
        if len(flashcards) >= count:
            break
            
    if len(flashcards) < count:
        total_text = "\n\n".join([p["text"] for p in pages_data if p["text"]])
        sentences = extract_key_sentences(total_text, max_sentences=count)
        for s in sentences:
            if len(flashcards) >= count:
                break
            tokens = tokenize(s)
            concept = tokens[0].capitalize() if tokens else "Key Principle"
            flashcards.append({
                "id": len(flashcards) + 1,
                "front": f"What is the significance of {concept} in these notes?",
                "back": s,
                "page": 1
            })
            
    return flashcards

# ==========================================
# BUILT-IN RAG CHATBOT (GROUNDED WITH CITATIONS)
# ==========================================

def answer_query_local(query: str, pages_data: List[Dict[str, Any]], doc_title: str) -> Dict[str, Any]:
    chunks = split_into_chunks(pages_data, chunk_size=120)
    retriever = TFIDFRetriever(chunks)
    results = retriever.search(query, top_k=3)
    
    # Check relevance threshold
    relevance_threshold = 1.2
    top_score = results[0][1] if results else 0.0
    
    citations = []
    for chunk, score in results:
        if score > 0.5:
            # Highlight snippet
            snip = chunk["text"][:180].strip()
            if len(chunk["text"]) > 180:
                snip += "..."
            citations.append({
                "page": chunk["page"],
                "snippet": snip,
                "score": round(score, 2)
            })
            
    if top_score < relevance_threshold or not citations:
        # Not in document!
        return {
            "answer": (
                f"⚠️ **Not Found in Document**: This specific question or topic does not appear to be covered in your uploaded notes (*{doc_title}*).\n\n"
                f"**General Academic Information**:\n"
                f"While your study material doesn't explicitly discuss this, here is a general explanation: "
                f"Regarding '{query}', this is typically related to broader foundational concepts. "
                f"Please verify if this topic is in another chapter or uploaded file!"
            ),
            "citations": [],
            "in_document": False
        }
        
    # Formulate answer from matched chunks with exact citations
    best_chunk = results[0][0]
    best_page = best_chunk["page"]
    
    # Extract relevant sentences from top chunks
    matched_sentences = []
    query_tokens = set(tokenize(query))
    for chunk, sc in results:
        chunk_sentences = re.split(r'(?<=[.!?])\s+', chunk["text"])
        for s in chunk_sentences:
            s_toks = set(tokenize(s))
            if s_toks & query_tokens and len(s) > 20:
                matched_sentences.append((s.strip(), chunk["page"]))
                
    if matched_sentences:
        answer_body = "\n\n".join([f"- {s[0]} *(Source: **Page {s[1]}**)*" for s in matched_sentences[:4]])
    else:
        answer_body = f"{best_chunk['text']} *(Source: **Page {best_page}**)*"
        
    formatted_answer = (
        f"Based on your notes in **{doc_title}**:\n\n"
        f"{answer_body}\n\n"
        f"💡 *See detailed citations below for direct page references.*"
    )
    
    return {
        "answer": formatted_answer,
        "citations": citations,
        "in_document": True
    }

# ==========================================
# EXTERNAL LLM INTEGRATION (GEMINI / OPENAI)
# ==========================================

def call_gemini_api(api_key: str, prompt: str, system_instruction: str = "") -> Optional[str]:
    api_key = api_key or DEFAULT_GEMINI_API_KEY
    if not api_key:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=65)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            print("Gemini API error:", resp.status_code, resp.text)
            return None
    except Exception as e:
        print("Gemini API request failed:", e)
        return None

def call_openai_api(api_key: str, prompt: str, system_instruction: str = "") -> Optional[str]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.3
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            return None
    except Exception as e:
        print("OpenAI API request failed:", e)
        return None

# ==========================================
# UNIFIED DISPATCHER
# ==========================================

def get_study_summary(pages_data: List[Dict[str, Any]], length: str, format_style: str, user: Dict[str, Any], doc_title: str) -> str:
    ai_provider = user.get("ai_provider", "gemini")
    gemini_key = user.get("gemini_api_key", "").strip() or DEFAULT_GEMINI_API_KEY
    openai_key = user.get("openai_api_key", "").strip()
    
    if (ai_provider == "gemini" or not ai_provider or ai_provider == "builtin") and gemini_key:
        doc_sample = "\n\n".join([f"[Page {p['page']}]: {p['text']}" for p in pages_data[:15]])
        prompt = (
            f"You are an elite academic professor and master AI Study Assistant. "
            f"Generate a thorough, high-yield, beautifully organized Study and Revision Guide for this document: '{doc_title}'.\n\n"
            f"Requested Length: {length} (short = concise executive summary; medium = balanced, structured conceptual notes; detailed = comprehensive exhaustive guide with all definitions and problem types).\n"
            f"Requested Format Style: {format_style} (bullet points, structured, or glossary).\n\n"
            f"Structure your guide into these clear, rich sections:\n"
            f"1. 📌 **Course & Subject Overview**: Identify the subject (e.g. Discrete Mathematical Structures, Engineering Mathematics, Computer Science), target audience, and primary scope.\n"
            f"2. 📑 **Module-by-Module / Chapter Synthesis**: Group content into clear logical modules/topics (e.g. Module 1: Propositional Logic & Tautologies, Module 2: Mathematical Induction & Recurrence Relations, Module 3: Functions & Relations, Module 4: Algebraic Structures & Group Theory).\n"
            f"3. 🔑 **Essential Definitions, Theorems & Formulas**: State the exact mathematical formulas, laws (e.g. De Morgan's Laws, Induction steps, Injective/Surjective/Bijective conditions, Klein-4 Group axioms), and definitions.\n"
            f"4. 🎯 **Key Problem Types & Exam Focus**: Detail the recurring problem types, proofs, and question formats seen in the document.\n"
            f"5. 💡 **Cheat-Sheet & Exam Tips**: High-yield takeaways and practical advice for scoring maximum marks.\n\n"
            f"Use clean GitHub Markdown with clear bold headers, bullet points, callout blockquotes, and LaTeX formatting for math formulas.\n\n"
            f"Study Document Text:\n{doc_sample}"
        )
        llm_resp = call_gemini_api(gemini_key, prompt, "You are a world-class university professor crafting top-tier study notes.")
        if llm_resp:
            return llm_resp

    if ai_provider == "openai" and openai_key:
        doc_sample = "\n\n".join([f"[Page {p['page']}]: {p['text']}" for p in pages_data[:15]])
        prompt = (
            f"Summarize this study document: '{doc_title}'. Length: {length}, format: {format_style}. "
            f"Extract key concepts, definitions, and page citations.\n\nDocument Text:\n{doc_sample}"
        )
        llm_resp = call_openai_api(openai_key, prompt)
        if llm_resp:
            return llm_resp

    return generate_local_summary(pages_data, length=length, format_style=format_style)

def get_study_chat_response(query: str, pages_data: List[Dict[str, Any]], user: Dict[str, Any], doc_title: str) -> Dict[str, Any]:
    ai_provider = user.get("ai_provider", "gemini")
    gemini_key = user.get("gemini_api_key", "").strip() or DEFAULT_GEMINI_API_KEY
    openai_key = user.get("openai_api_key", "").strip()
    
    chunks = split_into_chunks(pages_data, chunk_size=120)
    retriever = TFIDFRetriever(chunks)
    results = retriever.search(query, top_k=4)
    
    citations = []
    context_chunks = []
    for chunk, score in results:
        if score > 0.4:
            citations.append({
                "page": chunk["page"],
                "snippet": chunk["text"][:160] + ("..." if len(chunk["text"]) > 160 else ""),
                "score": round(score, 2)
            })
            context_chunks.append(f"[Page {chunk['page']}]: {chunk['text']}")
            
    is_in_doc = len(citations) > 0 and results[0][1] >= 1.0
    
    if gemini_key or (ai_provider == "openai" and openai_key):
        context_str = "\n\n".join(context_chunks) if context_chunks else "No strongly matching passages found in the notes."
        prompt = (
            f"Student Question: \"{query}\"\n"
            f"Uploaded Document: \"{doc_title}\"\n\n"
            f"Relevant Document Passages:\n{context_str}\n\n"
            f"CRITICAL INSTRUCTIONS:\n"
            f"1. If the answer is in the passages above, answer directly and cite the exact page number [Page X].\n"
            f"2. If the answer is NOT in the uploaded material, clearly state '⚠️ **Not found in document notes**: This topic is not mentioned in your uploaded study notes.', and then provide a brief, helpful answer based on general academic knowledge clearly identified as external knowledge."
        )
        if gemini_key:
            res = call_gemini_api(gemini_key, prompt, "You are an AI Study Assistant for university students.")
            if res:
                return {
                    "answer": res,
                    "citations": citations if is_in_doc else [],
                    "in_document": is_in_doc
                }
        if ai_provider == "openai" and openai_key:
            res = call_openai_api(openai_key, prompt)
            if res:
                return {
                    "answer": res,
                    "citations": citations if is_in_doc else [],
                    "in_document": is_in_doc
                }
                
    return answer_query_local(query, pages_data, doc_title)

def get_study_quiz(pages_data: List[Dict[str, Any]], quiz_type: str, count: int, user: Dict[str, Any], difficulty: str = "medium") -> Any:
    ai_provider = user.get("ai_provider", "gemini")
    gemini_key = user.get("gemini_api_key", "").strip() or DEFAULT_GEMINI_API_KEY
    
    if gemini_key:
        doc_sample = "\n\n".join([f"[Page {p['page']}]: {p['text']}" for p in pages_data[:12]])
        
        difficulty_instructions = {
            "easy": "Focus on core conceptual definitions, fundamental properties, and basic identification.",
            "medium": "Focus on standard university exam problems, applying formulas/theorems, and analyzing relationships.",
            "hard": "Focus on challenging multi-step questions, edge-cases, proof validation, and deep analytical problem-solving."
        }.get(difficulty, "Standard university exam level.")

        if quiz_type == "flashcards":
            prompt = (
                f"You are an expert tutor converting this study PDF into spaced repetition flashcards.\n"
                f"Generate {count} high-yield flashcards. Difficulty: {difficulty} ({difficulty_instructions}).\n"
                f"Return ONLY a valid JSON array of objects with keys: id (int), front (string: concept, law, or question), back (string: comprehensive clear explanation/definition), page (int: source page number).\n"
                f"Do NOT include markdown formatting or backticks, just return the raw JSON array.\n\n"
                f"Study Material:\n{doc_sample}"
            )
            raw = call_gemini_api(gemini_key, prompt)
            if raw:
                try:
                    clean_raw = raw.strip()
                    if clean_raw.startswith("```"):
                        clean_raw = re.sub(r"^```(?:json)?", "", clean_raw)
                        clean_raw = re.sub(r"```$", "", clean_raw).strip()
                    cards = json.loads(clean_raw)
                    if isinstance(cards, list) and len(cards) > 0:
                        return cards
                except Exception as e:
                    print("Gemini flashcard parse error:", e)

        elif quiz_type == "true_false":
            prompt = (
                f"You are a university professor converting this study PDF into a True/False exam quiz.\n"
                f"Generate {count} rigorous True/False questions. Difficulty: {difficulty} ({difficulty_instructions}).\n"
                f"Return ONLY a valid JSON array of objects with keys:\n"
                f"id (int), question (string statement), options (must be [\"True\", \"False\"]), answer (either 'A' for True or 'B' for False), explanation (string explaining why the statement is true or false with page reference), page (int: source page number).\n"
                f"Do NOT include markdown formatting or backticks, just return the raw JSON array.\n\n"
                f"Study Material:\n{doc_sample}"
            )
            raw = call_gemini_api(gemini_key, prompt)
            if raw:
                try:
                    clean_raw = raw.strip()
                    if clean_raw.startswith("```"):
                        clean_raw = re.sub(r"^```(?:json)?", "", clean_raw)
                        clean_raw = re.sub(r"```$", "", clean_raw).strip()
                    tf_items = json.loads(clean_raw)
                    if isinstance(tf_items, list) and len(tf_items) > 0:
                        return tf_items
                except Exception as e:
                    print("Gemini True/False parse error:", e)

        else: # MCQ
            prompt = (
                f"You are a university professor converting this study PDF into an interactive practice quiz.\n"
                f"Generate {count} multiple-choice exam questions directly based on the PDF content. Difficulty: {difficulty} ({difficulty_instructions}).\n"
                f"Return ONLY a valid JSON array of objects with keys:\n"
                f"id (int), question (string: clear question prompt), options (list of 4 distinct choices A, B, C, D with realistic plausible distractors), answer (one letter 'A', 'B', 'C', or 'D'), explanation (string explaining why the answer is correct with page reference), page (int: source page number).\n"
                f"Do NOT include markdown formatting or backticks, just return the raw JSON array.\n\n"
                f"Study Material:\n{doc_sample}"
            )
            raw = call_gemini_api(gemini_key, prompt)
            if raw:
                try:
                    clean_raw = raw.strip()
                    if clean_raw.startswith("```"):
                        clean_raw = re.sub(r"^```(?:json)?", "", clean_raw)
                        clean_raw = re.sub(r"```$", "", clean_raw).strip()
                    mcqs = json.loads(clean_raw)
                    if isinstance(mcqs, list) and len(mcqs) > 0:
                        return mcqs
                except Exception as e:
                    print("Gemini quiz parse error:", e)

    if quiz_type == "flashcards":
        return generate_local_flashcards(pages_data, count=count)
    else:
        return generate_local_quiz(pages_data, count=count)
