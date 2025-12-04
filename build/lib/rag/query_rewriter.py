import json
from typing import List

from agent.llm_client import SimpleLLMClient
from utils.prompt_loader import load_prompt


class QueryRewriter:
    def __init__(self, model_name: str):
        self.llm = SimpleLLMClient(model=model_name)

    def rewrite(self, original_task: str, num_queries: int = 4) -> List[str]:
        """
        Use LLM to decompose complex task into a hybrid list of queries (keywords, phrases, and sentences).
        """
        # 1. Load System Prompt
        system_prompt = load_prompt("rag_query_rewrite_system.md")
        
        # 2. Load User Prompt Template and Format
        # Use replace instead of format to avoid issues with JSON braces in the prompt
        user_prompt_template = load_prompt("rag_query_rewrite_user.md")
        prompt = user_prompt_template.replace("{original_task}", original_task)
        prompt = prompt.replace("{num_queries}", str(num_queries))
        
        try:
            # Call LLM
            response = self.llm.generate(prompt, system_prompt)
            
            # Clean Markdown format
            content = response.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"): 
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            queries = json.loads(content.strip())
            
            if isinstance(queries, list):
                return queries
            else:
                return [original_task]
                
        except Exception as e:
            print(f"Query rewrite failed: {e}. Fallback to original task.")
            # Fallback strategy
            return [original_task]
