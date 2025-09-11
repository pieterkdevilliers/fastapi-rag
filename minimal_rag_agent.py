# # minimal_rag_agent.py
# """
# Minimal working example of a Pydantic-AI agent with a simple RAG tool.
# This doesn't depend on your existing models to avoid circular import issues.
# """

# import os
# import asyncio
# from dotenv import load_dotenv
# from pydantic_ai import Agent, RunContext
# from pydantic import BaseModel
# from typing import List, Optional
# from dataclasses import dataclass

# # Load environment variables
# load_dotenv()

# # Verify API key
# if not os.getenv('OPENAI_API_KEY'):
#     print("❌ OPENAI_API_KEY not found in environment variables")
#     print("   Please ensure your .env file contains: OPENAI_API_KEY=your_key_here")
#     exit(1)

# CHAT_MODEL_NAME = os.environ.get('OPENAI_CHAT_MODEL', 'gpt-3.5-turbo')
# print(f"Using OpenAI chat model: {CHAT_MODEL_NAME}")

# # === PYDANTIC MODELS ===

# class RAGQueryInput(BaseModel):
#     """Input for the RAG search tool"""
#     query: str
#     max_results: Optional[int] = 3

# class RAGQueryOutput(BaseModel):
#     """Output from the RAG search tool"""
#     query: str
#     response_text: str
#     sources: List[str]
#     context_used: str

# # === MOCK DATA (Replace with your real data) ===

# # This simulates your knowledge base - replace with real Chroma/vector DB calls
# MOCK_KNOWLEDGE_BASE = {
#     "company policy": [
#         {
#             "content": "Our company vacation policy allows 25 days of paid time off per year. Employees must request vacation at least 2 weeks in advance.",
#             "source": "HR_Manual_2024.pdf"
#         },
#         {
#             "content": "Sick leave is unlimited but requires a doctor's note for absences longer than 3 consecutive days.",
#             "source": "Employee_Handbook.pdf"
#         }
#     ],
#     "machine learning": [
#         {
#             "content": "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed.",
#             "source": "ML_Guide.pdf"
#         },
#         {
#             "content": "Common ML algorithms include linear regression, decision trees, neural networks, and support vector machines.",
#             "source": "Algorithms_Overview.pdf"
#         }
#     ],
#     "python": [
#         {
#             "content": "Python is a high-level programming language known for its simplicity and readability. It's widely used in data science, web development, and automation.",
#             "source": "Python_Basics.pdf"
#         }
#     ]
# }

# def mock_vector_search(query: str, max_results: int = 3) -> List[dict]:
#     """
#     Mock function that simulates vector search.
#     In your real implementation, this would call Chroma/OpenAI embeddings.
#     """
#     query_lower = query.lower()
#     results = []
    
#     # Simple keyword matching (replace with actual vector similarity)
#     for topic, documents in MOCK_KNOWLEDGE_BASE.items():
#         if topic in query_lower or any(word in topic for word in query_lower.split()):
#             results.extend(documents)
    
#     # Limit results
#     return results[:max_results]

# # === SIMPLE AGENT STATE ===

# @dataclass
# class SimpleAgentState:
#     """Simplified agent state for demo purposes"""
#     user_id: str
#     chat_history: List[dict]

# # === CREATE AGENT ===

# agent = Agent(
#     f'openai:{CHAT_MODEL_NAME}',
#     system_prompt="""You are an intelligent assistant with access to a company knowledge base.

# When users ask questions that might be answered by company documents or technical information:
# - Use the 'rag_search' tool to find relevant information
# - Provide helpful answers based on the retrieved context
# - Always cite your sources when using information from the knowledge base
# - If no relevant information is found, say so clearly

# For general conversation or questions that don't require specific knowledge base information, answer normally.""",
# )

# # === RAG TOOL ===

# @agent.tool
# async def rag_search(ctx: RunContext[SimpleAgentState], input_data: RAGQueryInput) -> RAGQueryOutput:
#     """
#     Search the knowledge base for relevant information.
    
#     This tool demonstrates the RAG pattern:
#     1. Take a query
#     2. Search for relevant documents (mock implementation)
#     3. Generate a response based on the retrieved context
#     """
    
#     print(f"🔍 RAG Tool called with query: '{input_data.query}'")
    
#     # Get agent state
#     state = ctx.deps
#     print(f"   User: {state.user_id}")
    
#     # Mock vector search (replace with your real Chroma search)
#     search_results = mock_vector_search(input_data.query, input_data.max_results)
    
#     if not search_results:
#         return RAGQueryOutput(
#             query=input_data.query,
#             response_text=f"No relevant information found for: {input_data.query}",
#             sources=[],
#             context_used=""
#         )
    
#     # Build context from search results
#     context_parts = []
#     sources = []
    
#     for result in search_results:
#         context_parts.append(f"Source: {result['source']}\n{result['content']}")
#         sources.append(result['source'])
    
#     context_text = "\n\n---\n\n".join(context_parts)
    
#     # For this demo, we'll use a simple prompt-based approach
#     # In your real implementation, you can integrate this with your existing LangChain setup
#     response_text = f"Based on the available information:\n\n{context_text}"
    
#     print(f"✅ RAG Tool found {len(search_results)} relevant documents")
    
#     return RAGQueryOutput(
#         query=input_data.query,
#         response_text=response_text,
#         sources=sources,
#         context_used=context_text
#     )

# # === DEMO FUNCTIONS ===

# async def demo_conversation():
#     """Demo conversation showing the agent in action"""
    
#     print("\n🤖 Starting Pydantic-AI RAG Agent Demo")
#     print("=" * 60)
    
#     # Create agent state
#     state = SimpleAgentState(
#         user_id="demo_user",
#         chat_history=[]
#     )
    
#     # Test queries
#     test_queries = [
#         "What is our company vacation policy?",
#         "Tell me about machine learning",
#         "What's the weather like today?",  # This shouldn't trigger RAG
#         "How do I use Python for data science?",
#     ]
    
#     for query in test_queries:
#         print(f"\n👤 User: {query}")
#         print("🤖 Agent: ", end="")
        
#         try:
#             # Run the agent
#             result = await agent.run(query, deps=state)
#             print(result.data)
            
#             # Show what tools were used
#             messages = result.all_messages()
#             tool_calls = [msg for msg in messages if hasattr(msg, 'content') and 'rag_search' in str(msg.content)]
            
#             if tool_calls:
#                 print("   🔧 Used RAG tool")
#             else:
#                 print("   💭 Used general knowledge")
                
#         except Exception as e:
#             print(f"❌ Error: {e}")
        
#         print("-" * 40)

# async def interactive_demo():
#     """Interactive demo where you can ask questions"""
    
#     print("\n🎯 Interactive RAG Agent Demo")
#     print("Type 'quit' to exit, 'help' for commands")
#     print("=" * 60)
    
#     state = SimpleAgentState(
#         user_id="interactive_user",
#         chat_history=[]
#     )
    
#     while True:
#         try:
#             query = input("\n👤 You: ").strip()
            
#             if query.lower() == 'quit':
#                 print("👋 Goodbye!")
#                 break
#             elif query.lower() == 'help':
#                 print("📋 Try asking about:")
#                 print("   • Company vacation policy")
#                 print("   • Machine learning")
#                 print("   • Python programming")
#                 print("   • Or any general question")
#                 continue
#             elif not query:
#                 continue
            
#             print("🤖 Agent: ", end="", flush=True)
#             result = await agent.run(query, deps=state)
            
#             # Handle different result attribute names
#             response_text = None
#             if hasattr(result, 'data'):
#                 response_text = result.data
#             elif hasattr(result, 'response'):
#                 response_text = result.response
#             elif hasattr(result, 'content'):
#                 response_text = result.content
#             else:
#                 response_text = str(result)
                
#             print(response_text)
            
#         except KeyboardInterrupt:
#             print("\n👋 Goodbye!")
#             break
#         except Exception as e:
#             print(f"❌ Error: {e}")

# def main():
#     """Main function with demo options"""
    
#     print("🚀 Pydantic-AI RAG Agent Demo")
#     print("Choose an option:")
#     print("1. Run automated demo")
#     print("2. Interactive chat")
#     print("3. Exit")
    
#     while True:
#         choice = input("\nEnter choice (1-3): ").strip()
        
#         if choice == '1':
#             asyncio.run(demo_conversation())
#             break
#         elif choice == '2':
#             asyncio.run(interactive_demo())
#             break
#         elif choice == '3':
#             print("👋 Goodbye!")
#             break
#         else:
#             print("Invalid choice. Please enter 1, 2, or 3.")

# if __name__ == "__main__":
#     main()