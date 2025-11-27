"""
LangGraph-based GraphRAG Pipeline for Insurance Policy QA
"""
from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from loguru import logger
import json

from src.config.settings import settings
from src.retrieval.hybrid_retriever import HybridRetriever


class GraphRAGState(TypedDict):
    """State for the GraphRAG pipeline"""
    question: str
    query_scope: str  # "product_overview" or "clause_detail"
    intent: str  # coverage, exclusion, condition, etc.
    keywords: List[str]
    risk_types: List[str]
    special_clause: str
    clause_mentioned: str
    retrieved_chunks: List[Dict[str, Any]]
    answer: str
    citations: List[Dict[str, Any]]
    confidence: float


class PolicyGraphRAGPipeline:
    """
    LangGraph-based pipeline for policy QA using GraphRAG
    """
    
    QUERY_ROUTER_PROMPT = """You are an expert at understanding insurance-related questions.

Determine whether the user is asking about:
1. **product_overview**: General questions about the insurance product itself
   - What is this insurance product?
   - What are the main features?
   - What does this insurance cover in general?
   - How much is the premium?
   - What is the general coverage?
   
2. **clause_detail**: Specific questions requiring detailed clause interpretation
   - Specific coverage details for certain situations
   - Exclusion conditions
   - Claim procedures
   - Specific requirements or conditions
   - Detailed interpretation of specific clauses

Question: {question}

Return ONLY a JSON object:
{{
  "query_scope": "product_overview" or "clause_detail",
  "reasoning": "brief explanation of why"
}}
"""
    
    QUERY_UNDERSTANDING_PROMPT = """You are an expert at analyzing insurance policy questions.

Analyze the following question and extract:
1. Intent: What is the user asking about?
   - "coverage": What is covered/compensated
   - "exclusion": What is NOT covered/excluded
   - "condition": Conditions, requirements, or procedures
   - "deductible": Self-payment amounts
   - "limit": Coverage limits
   - "definition": Term definitions
   - "general": General questions

2. Keywords: Important terms (in Korean)

3. Risk Types: What risks are mentioned? (화재, 도난, 풍수해, 지진 etc.)

4. Special Clause: Is a specific special clause (특약) mentioned?

5. Clause Number: Is a specific clause number mentioned? (e.g., 제11조, 제2조)

Question: {question}

Return a JSON object with these fields:
{{
  "intent": "coverage|exclusion|condition|deductible|limit|definition|general",
  "keywords": ["keyword1", "keyword2", ...],
  "risk_types": ["risk1", "risk2", ...],
  "special_clause": "name of special clause or null",
  "clause_mentioned": "제X조 or null"
}}
"""
    
    ANSWER_SYNTHESIS_PROMPT = """You are an insurance policy expert assistant. 

Based on the retrieved policy clauses, answer the user's question accurately and clearly.

IMPORTANT RULES:
1. Answer ONLY based on the provided policy clauses
2. Always cite the specific clause (조항) for each statement
3. Organize your answer by:
   - Coverage (보상내용)
   - Exclusions (면책사항)
   - Conditions (조건/요건)
   - Additional Notes (참고사항)

4. Use clear, professional Korean
5. If information is not found, say so clearly

Question: {question}

Retrieved Policy Clauses:
{context}

Provide your answer in the following JSON format:
{{
  "answer": "your detailed answer here",
  "coverage": ["coverage point 1", "coverage point 2", ...],
  "exclusions": ["exclusion 1", "exclusion 2", ...],
  "conditions": ["condition 1", "condition 2", ...],
  "citations": [
    {{"clause_id": "제X조", "title": "title", "text": "relevant excerpt"}}
  ],
  "confidence": 0.0-1.0
}}
"""
    
    def __init__(self):
        """Initialize the pipeline"""
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=0.1,
            api_key=settings.openai_api_key
        )
        
        self.retriever = HybridRetriever(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            alpha=settings.hybrid_alpha
        )
        
        # Build the graph
        self.graph = self._build_graph()
        
        logger.info("✅ PolicyGraphRAGPipeline initialized")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow with routing"""
        workflow = StateGraph(GraphRAGState)
        
        # Add nodes
        workflow.add_node("query_router", self._query_router_node)
        workflow.add_node("query_understanding", self._query_understanding_node)
        workflow.add_node("product_retrieval", self._product_retrieval_node)
        workflow.add_node("clause_retrieval", self._clause_retrieval_node)
        workflow.add_node("answer_synthesis", self._answer_synthesis_node)
        
        # Add edges
        workflow.set_entry_point("query_router")
        
        # Conditional routing based on query_scope
        workflow.add_conditional_edges(
            "query_router",
            self._route_query,
            {
                "product_overview": "product_retrieval",
                "clause_detail": "query_understanding"
            }
        )
        
        # Product overview path
        workflow.add_edge("product_retrieval", "answer_synthesis")
        
        # Clause detail path
        workflow.add_edge("query_understanding", "clause_retrieval")
        workflow.add_edge("clause_retrieval", "answer_synthesis")
        
        # End
        workflow.add_edge("answer_synthesis", END)
        
        return workflow.compile()
    
    def _query_router_node(self, state: GraphRAGState) -> GraphRAGState:
        """
        Node 0: Route query to product overview or clause detail path
        """
        logger.info("🚦 Query Router Node")
        
        question = state["question"]
        
        prompt = ChatPromptTemplate.from_template(self.QUERY_ROUTER_PROMPT)
        
        try:
            response = self.llm.invoke(
                prompt.format(question=question),
            )
            
            # Parse JSON response
            content = response.content
            
            # Extract JSON from response
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
            
            parsed = json.loads(json_str)
            
            state["query_scope"] = parsed.get("query_scope", "clause_detail")
            logger.info(f"Routed to: {state['query_scope']} - {parsed.get('reasoning', '')}")
            
        except Exception as e:
            logger.error(f"Error in query routing: {e}")
            # Default to clause detail
            state["query_scope"] = "clause_detail"
        
        return state
    
    def _route_query(self, state: GraphRAGState) -> str:
        """
        Routing function to determine next node
        """
        return state.get("query_scope", "clause_detail")
    
    def _query_understanding_node(self, state: GraphRAGState) -> GraphRAGState:
        """
        Node 1: Understand the query and extract structured information (for clause detail)
        """
        logger.info("🔍 Query Understanding Node")
        
        question = state["question"]
        
        prompt = ChatPromptTemplate.from_template(self.QUERY_UNDERSTANDING_PROMPT)
        
        try:
            response = self.llm.invoke(
                prompt.format(question=question),
            )
            
            # Parse JSON response
            content = response.content
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
            
            parsed = json.loads(json_str)
            
            state["intent"] = parsed.get("intent", "general")
            state["keywords"] = parsed.get("keywords", [])
            state["risk_types"] = parsed.get("risk_types", [])
            state["special_clause"] = parsed.get("special_clause", "")
            state["clause_mentioned"] = parsed.get("clause_mentioned", "")
            
            logger.info(f"Extracted intent: {state['intent']}, keywords: {state['keywords']}")
            
        except Exception as e:
            logger.error(f"Error in query understanding: {e}")
            # Fallback
            state["intent"] = "general"
            state["keywords"] = []
            state["risk_types"] = []
            state["special_clause"] = ""
            state["clause_mentioned"] = ""
        
        return state
    
    def _product_retrieval_node(self, state: GraphRAGState) -> GraphRAGState:
        """
        Node 2a: Retrieve product-level information using HyDE
        """
        logger.info("📦 Product Retrieval Node (HyDE)")
        
        question = state["question"]
        
        try:
            # Search in InsuranceProduct and HypotheticalQuestion nodes
            results = self.retriever.retrieve_product_overview(question)
            
            state["retrieved_chunks"] = results
            state["intent"] = "general"
            logger.info(f"Retrieved product overview with {len(results)} items")
            
        except Exception as e:
            logger.error(f"Error in product retrieval: {e}")
            state["retrieved_chunks"] = []
            state["intent"] = "general"
        
        return state
    
    def _clause_retrieval_node(self, state: GraphRAGState) -> GraphRAGState:
        """
        Node 2b: Retrieve relevant chunks using hybrid retrieval (for clause detail)
        """
        logger.info("📚 Clause Retrieval Node")
        
        question = state["question"]
        intent = state.get("intent", "general")
        
        # Determine clause type filter
        clause_type_map = {
            "coverage": "Coverage",
            "exclusion": "Exclusion",
            "condition": "Condition",
            "definition": "Definition"
        }
        
        filter_clause_type = clause_type_map.get(intent)
        
        # Retrieve chunks
        try:
            results = self.retriever.retrieve(
                query=question,
                top_k=settings.retrieval_top_k,
                intent=intent,
                filter_clause_type=filter_clause_type
            )
            
            state["retrieved_chunks"] = results
            logger.info(f"Retrieved {len(results)} chunks")
            
        except Exception as e:
            logger.error(f"Error in retrieval: {e}")
            state["retrieved_chunks"] = []
        
        return state
    
    def _answer_synthesis_node(self, state: GraphRAGState) -> GraphRAGState:
        """
        Node 3: Synthesize answer from retrieved chunks or product info
        """
        logger.info("✍️  Answer Synthesis Node")
        
        question = state["question"]
        chunks = state.get("retrieved_chunks", [])
        query_scope = state.get("query_scope", "clause_detail")
        
        if not chunks:
            state["answer"] = "죄송합니다. 관련된 약관 정보를 찾을 수 없습니다."
            state["citations"] = []
            state["confidence"] = 0.0
            return state
        
        # Check if product overview result
        if chunks and chunks[0].get('type') == 'product_overview':
            logger.info("Synthesizing answer from product overview")
            
            product_data = chunks[0].get('product', {})
            matched_questions = chunks[0].get('matched_questions', [])
            
            # Generate answer based on product summary
            answer_parts = []
            answer_parts.append(f"**{product_data.get('name', '보험상품')}**")
            answer_parts.append("")
            answer_parts.append(product_data.get('summary', '상품 정보를 찾을 수 없습니다.'))
            
            if matched_questions:
                answer_parts.append("")
                answer_parts.append("💡 관련 질문:")
                for i, mq in enumerate(matched_questions[:3], 1):
                    answer_parts.append(f"  {i}. {mq['question']}")
            
            state["answer"] = "\n".join(answer_parts)
            state["citations"] = [{
                "clause_id": "상품정보",
                "title": product_data.get('name', ''),
                "text": product_data.get('summary', '')[:100]
            }]
            state["confidence"] = chunks[0].get('hybrid_score', 0.9)
            
            logger.info(f"Product overview answer generated with confidence: {state['confidence']}")
            return state
        
        # Clause detail answer (기존 로직)
        # Format context
        context_parts = []
        for i, chunk in enumerate(chunks):
            clause = chunk.get('clause', {})
            chunk_data = chunk.get('chunk', {})
            
            context_parts.append(
                f"[{i+1}] {clause.get('clauseId', 'N/A')} - {clause.get('title', 'N/A')}\n"
                f"유형: {clause.get('clauseType', 'N/A')}\n"
                f"내용: {chunk_data.get('text', '')}\n"
            )
        
        context = "\n---\n".join(context_parts)
        
        prompt = ChatPromptTemplate.from_template(self.ANSWER_SYNTHESIS_PROMPT)
        
        try:
            response = self.llm.invoke(
                prompt.format(question=question, context=context)
            )
            
            content = response.content
            
            # Extract JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()
            
            parsed = json.loads(json_str)
            
            state["answer"] = parsed.get("answer", "답변을 생성할 수 없습니다.")
            state["citations"] = parsed.get("citations", [])
            state["confidence"] = parsed.get("confidence", 0.5)
            
            logger.info(f"Answer generated with confidence: {state['confidence']}")
            
        except Exception as e:
            logger.error(f"Error in answer synthesis: {e}")
            # Fallback: simple concatenation
            state["answer"] = "검색된 약관 내용:\n\n" + context[:1000]
            state["citations"] = [
                {
                    "clause_id": chunk.get('clause', {}).get('clauseId', 'N/A'),
                    "title": chunk.get('clause', {}).get('title', 'N/A')
                }
                for chunk in chunks[:3]
            ]
            state["confidence"] = 0.3
        
        return state
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        Run the complete pipeline for a question
        
        Args:
            question: User question
            
        Returns:
            Dictionary with answer, citations, and metadata
        """
        logger.info(f"🚀 Processing question: {question}")
        
        # Initialize state
        initial_state = {
            "question": question,
            "query_scope": "",
            "intent": "",
            "keywords": [],
            "risk_types": [],
            "special_clause": "",
            "clause_mentioned": "",
            "retrieved_chunks": [],
            "answer": "",
            "citations": [],
            "confidence": 0.0
        }
        
        # Run the graph
        final_state = self.graph.invoke(initial_state)
        
        # Format result
        result = {
            "question": question,
            "answer": final_state.get("answer", ""),
            "intent": final_state.get("intent", ""),
            "citations": final_state.get("citations", []),
            "confidence": final_state.get("confidence", 0.0),
            "retrieved_chunks_count": len(final_state.get("retrieved_chunks", []))
        }
        
        logger.info(f"✅ Query complete. Confidence: {result['confidence']}")
        
        return result
    
    def close(self):
        """Clean up resources"""
        self.retriever.close()
        logger.info("Pipeline closed")


if __name__ == "__main__":
    # Example usage
    pipeline = PolicyGraphRAGPipeline()
    
    # Test questions
    questions = [
        "화재로 인한 손해를 보상받을 수 있나요?",
        "도난위험 특약에서 보상하지 않는 경우는 무엇인가요?",
        "제11조의 내용은 무엇인가요?"
    ]
    
    for q in questions:
        print(f"\n{'='*60}")
        print(f"질문: {q}")
        print(f"{'='*60}")
        
        result = pipeline.query(q)
        
        print(f"\n답변:\n{result['answer']}\n")
        print(f"신뢰도: {result['confidence']:.2f}")
        print(f"인용: {len(result['citations'])}개 조항")
        
        if result['citations']:
            print("\n참조 조항:")
            for citation in result['citations'][:3]:
                print(f"  - {citation.get('clause_id', 'N/A')}: {citation.get('title', 'N/A')}")
    
    pipeline.close()
