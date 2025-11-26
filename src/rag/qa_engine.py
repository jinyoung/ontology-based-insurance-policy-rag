"""
Policy QA Engine
Main interface for policy question answering
"""
from typing import Dict, Any, List, Optional
from loguru import logger
from src.rag.langgraph_pipeline import PolicyGraphRAGPipeline


class PolicyQAEngine:
    """
    Main QA engine for insurance policy questions
    """
    
    def __init__(self):
        """Initialize the QA engine"""
        self.pipeline = PolicyGraphRAGPipeline()
        logger.info("✅ PolicyQAEngine initialized")
    
    def query(self, question: str, **kwargs) -> Dict[str, Any]:
        """
        Answer a policy question
        
        Args:
            question: User question
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with answer and metadata
        """
        return self.pipeline.query(question)
    
    def batch_query(self, questions: List[str]) -> List[Dict[str, Any]]:
        """
        Answer multiple questions
        
        Args:
            questions: List of questions
            
        Returns:
            List of results
        """
        results = []
        for question in questions:
            result = self.query(question)
            results.append(result)
        
        return results
    
    def close(self):
        """Clean up resources"""
        self.pipeline.close()
        logger.info("QA Engine closed")


if __name__ == "__main__":
    # Example usage
    engine = PolicyQAEngine()
    
    result = engine.query("화재보험에서 보상하는 손해는 무엇인가요?")
    
    print(f"질문: {result['question']}")
    print(f"\n답변:\n{result['answer']}")
    print(f"\n신뢰도: {result['confidence']:.2f}")
    
    engine.close()
