import os
import json
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv

# Import database search functions
from db import search_chunks, get_openai_client, get_gemini_client, AI_PROVIDER

load_dotenv(override=True)

# Pydantic schema for structured agent output
class RecommendedProduct(BaseModel):
    name: str = Field(description="Name of the electrical product or component (e.g. MasterPact MTZ2, TeSys Deca)")
    part_number: str = Field(description="Catalog number, model code, or part number (e.g. MTZ2 16 H1, LRD33)")
    specs: str = Field(description="Key technical parameters (e.g. 1600 A, 690 V, 3-pole, overload range 23-32A)")
    pdf_source: str = Field(description="The source catalog filename and page number (e.g. 'SE9661-MTZ-Catalogue.pdf, Page 24')")
    match_reason: str = Field(description="Brief explanation of why this component fits the user's needs")

class AgentResponse(BaseModel):
    chat_response: str = Field(description="The conversational text response to the user. Address their query, explain the products if recommending them, and ask 1 or 2 clear follow-up questions if you need to narrow down their requirements.")
    recommendations: List[RecommendedProduct] = Field(description="List of the top 3 recommended products matching their needs. Return empty list if you need to ask follow-up questions first, or if there are no matches.")

SYSTEM_PROMPT = """You are a professional Customer Product Discovery Agent representing an electrical components manufacturer/distributor.
Your goal is to help customers identify the exact electrical products (e.g. circuit breakers, contactors, overloads, switches) they need from our catalog.

Here is your operational workflow:
1. Review the conversation history and the latest user query.
2. Read the retrieved Technical Context from the product manuals.
3. If the user's request is broad (e.g., "I need a circuit breaker"), DO NOT jump straight to final recommendations. Instead, ask 1 or 2 relevant follow-up questions to narrow down their technical constraints (e.g., current rating, voltage, number of poles, installation type, breaking capacity).
4. If you have enough technical details, identify the top 3 most suitable products from the context.
5. In your `chat_response`, explain the options in a helpful, professional tone.
6. In the `recommendations` list, output up to 3 structured products with part numbers, key specifications, PDF source citation (name and page number), and a specific match reason.
7. Only recommend products that actually exist in the retrieved Technical Context. Do not invent products.

Remember:
- Be precise with technical terms.
- Keep the user engaged by asking clarifying questions when requirements are underspecified.
- Limit recommendations to at most 3 items.
"""

def build_prompt(history: list[dict], user_message: str, context_str: str) -> str:
    """
    Construct the final prompt for the LLM.
    """
    history_str = ""
    for msg in history:
        role = "Customer" if msg["role"] == "user" else "Agent"
        history_str += f"{role}: {msg['content']}\n"
        
    prompt = f"""{SYSTEM_PROMPT}

--- TECHNICAL CONTEXT FROM MANUALS ---
{context_str}
--------------------------------------

--- CONVERSATION HISTORY ---
{history_str}Customer: {user_message}
Agent: (Think about the customer's request, check the technical context, formulate the response)
"""
    return prompt

def run_agent(history: list[dict], user_message: str) -> AgentResponse:
    """
    Run the product discovery agent using search + LLM.
    """
    # 1. Expand query and search DB
    # We use the user's current message and optionally some context from history for search
    search_query = user_message
    if history:
        # Simple query expansion: append the last user question if relevant
        last_user_msgs = [m["content"] for m in history if m["role"] == "user"]
        if last_user_msgs:
            search_query = f"{last_user_msgs[-1]} {user_message}"
            
    # Perform vector search
    retrieved_chunks = search_chunks(search_query, limit=8)
    
    # Format context
    context_str = ""
    if retrieved_chunks:
        for idx, chunk in enumerate(retrieved_chunks):
            context_str += f"[Doc {idx+1}] Source: {chunk['pdf_name']}, Page: {chunk['page_num']}\nText:\n{chunk['text']}\n\n"
    else:
        context_str = "No relevant context found in database. The database may be empty or indexing is required."

    # 2. Build Prompt
    prompt = build_prompt(history, user_message, context_str)
    
    # 3. Call Cloud Model with Structured Output
    if AI_PROVIDER == "openai":
        client = get_openai_client()
        model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        
        try:
            response = client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a structured product discovery assistant."},
                    {"role": "user", "content": prompt}
                ],
                response_format=AgentResponse,
                temperature=0.2
            )
            return response.choices[0].message.parsed
        except Exception as e:
            print(f"OpenAI agent call failed: {e}")
            # Return a fallback response
            return AgentResponse(
                chat_response=f"I encountered an error calling the OpenAI service: {str(e)}",
                recommendations=[]
            )
            
    elif AI_PROVIDER == "gemini":
        client = get_gemini_client()
        model = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
        
        try:
            from google.genai import types
            
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AgentResponse,
                    temperature=0.2
                )
            )
            
            # Parse response text manually as pydantic validation
            data = json.loads(response.text)
            return AgentResponse.model_validate(data)
            
        except Exception as e:
            print(f"Gemini agent call failed: {e}")
            return AgentResponse(
                chat_response=f"I encountered an error calling the Gemini service: {str(e)}",
                recommendations=[]
            )
    else:
        raise ValueError(f"Unknown AI_PROVIDER: {AI_PROVIDER}")
