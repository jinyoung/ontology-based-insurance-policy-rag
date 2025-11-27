"""
Hybrid Retriever combining Graph and Vector Search
"""
from typing import List, Dict, Any, Optional, Tuple
from neo4j import GraphDatabase
from openai import OpenAI
from loguru import logger
from src.config.settings import settings


class HybridRetriever:
    """
    Combines graph-based and vector-based retrieval for optimal results
    """
    
    def __init__(self, uri: str, username: str, password: str, alpha: float = 0.5):
        """
        Initialize hybrid retriever
        
        Args:
            uri: Neo4j URI
            username: Neo4j username
            password: Neo4j password
            alpha: Weight for combining scores (0=graph only, 1=vector only)
        """
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        self.alpha = alpha
        logger.info(f"HybridRetriever initialized with alpha={alpha}")
    
    def retrieve(self, 
                     query: str,
                 top_k: int = 10,
                 intent: Optional[str] = None,
                 filter_clause_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval combining graph and vector search
        
        Args:
            query: User query
            top_k: Number of results to return
            intent: Query intent (coverage, exclusion, condition, etc.)
            filter_clause_type: Filter by clause type
            
        Returns:
            List of retrieved chunks with scores and metadata
        """
        # Step 1: Generate query embedding
        query_embedding = self._generate_embedding(query)
        
        # Step 2: Vector search
        vector_results = self._vector_search(query_embedding, top_k * 2, filter_clause_type)
        
        # Step 3: Graph-based filtering/expansion
        graph_results = self._graph_filter(query, intent, top_k * 2)
        
        # Step 4: Combine and rank
        combined_results = self._combine_results(vector_results, graph_results, top_k)
        
        logger.info(f"Hybrid retrieval returned {len(combined_results)} results")
        return combined_results
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for query text"""
        try:
            response = self.openai_client.embeddings.create(
                model=settings.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def _vector_search(self,
                       query_embedding: List[float],
                       top_k: int,
                       filter_clause_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search on Neo4j
        
        Args:
            query_embedding: Query vector
            top_k: Number of results
            filter_clause_type: Optional clause type filter
            
        Returns:
            List of results with scores
        """
        with self.driver.session() as session:
            try:
                # Try to use vector index if available
                if filter_clause_type:
                    cypher_query = """
                        CALL db.index.vector.queryNodes('paragraph_embedding_index', $top_k, $query_embedding)
                        YIELD node, score
                        MATCH (node)<-[:HAS_PARAGRAPH]-(c:PolicyClause)
                        WHERE c.clauseType = $clause_type
                        RETURN node, score, c
                        ORDER BY score DESC
                    """
                    result = session.run(
                        cypher_query,
                        top_k=top_k,
                        query_embedding=query_embedding,
                        clause_type=filter_clause_type
                    )
                else:
                    cypher_query = """
                        CALL db.index.vector.queryNodes('paragraph_embedding_index', $top_k, $query_embedding)
                        YIELD node, score
                        MATCH (node)<-[:HAS_PARAGRAPH]-(c:PolicyClause)
                        RETURN node, score, c
                        ORDER BY score DESC
                    """
                    result = session.run(
                        cypher_query,
                        top_k=top_k,
                        query_embedding=query_embedding
                    )
                
                results = []
                for record in result:
                    results.append({
                        'chunk': dict(record['node']),
                        'vector_score': record['score'],
                        'clause': dict(record['c']),
                        'source': 'vector'
                    })
                
                logger.debug(f"Vector search returned {len(results)} results")
                return results
                
            except Exception as e:
                # Fallback: manual cosine similarity if vector index not available
                logger.warning(f"Vector index not available, using manual similarity: {e}")
                return self._manual_vector_search(query_embedding, top_k, filter_clause_type)
    
    def _graph_filter(self, 
                      query: str,
                      intent: Optional[str],
                      top_k: int) -> List[Dict[str, Any]]:
        """
        Graph-based filtering using keywords and intent
        
        Args:
            query: User query
            intent: Query intent
            top_k: Number of results
            
        Returns:
            List of graph-filtered results
        """
        # Extract keywords from query
        keywords = self._extract_keywords(query)
        
        with self.driver.session() as session:
            # Build keyword-based search
            if intent == 'coverage':
                clause_type_filter = "c.clauseType = 'Coverage'"
            elif intent == 'exclusion':
                clause_type_filter = "c.clauseType = 'Exclusion'"
            elif intent == 'condition':
                clause_type_filter = "c.clauseType = 'Condition'"
            else:
                clause_type_filter = "1=1"
            
            # Search based on keywords
            keyword_conditions = " OR ".join([
                f"c.text CONTAINS '{kw}' OR c.title CONTAINS '{kw}'"
                for kw in keywords if kw
            ])
            
            if not keyword_conditions:
                keyword_conditions = "1=1"
            
            cypher_query = f"""
                MATCH (c:PolicyClause)-[:HAS_PARAGRAPH]->(p:ParagraphChunk)
                WHERE {clause_type_filter}
                  AND ({keyword_conditions})
                RETURN p, c
            LIMIT $top_k
            """
            
            result = session.run(cypher_query, top_k=top_k)
            
            results = []
            for record in result:
                results.append({
                    'chunk': dict(record['p']),
                    'graph_score': 1.0,  # Simple scoring
                    'clause': dict(record['c']),
                    'source': 'graph'
                })
            
            logger.debug(f"Graph search returned {len(results)} results")
            return results
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract important keywords from query"""
        # Simple keyword extraction (can be enhanced with NLP)
        import re
        
        # Remove common words
        stopwords = {'은', '는', '이', '가', '을', '를', '의', '에', '에서', '로', '으로', '와', '과'}
        
        # Split and clean
        words = re.findall(r'[가-힣]+', query)
        keywords = [w for w in words if w not in stopwords and len(w) > 1]
        
        return keywords[:5]  # Return top 5 keywords
    
    def _combine_results(self,
                        vector_results: List[Dict[str, Any]],
                        graph_results: List[Dict[str, Any]],
                        top_k: int) -> List[Dict[str, Any]]:
        """
        Combine and rank results from vector and graph search
        
        Args:
            vector_results: Results from vector search
            graph_results: Results from graph search
            top_k: Number of final results
            
        Returns:
            Combined and ranked results
        """
        # Create a dictionary to merge results by chunk_id
        combined = {}
        
        # Add vector results
        for result in vector_results:
            chunk_id = result['chunk'].get('chunkId')
            if chunk_id:
                combined[chunk_id] = {
                    **result,
                    'vector_score': result.get('vector_score', 0),
                    'graph_score': 0
                }
        
        # Add/merge graph results
        for result in graph_results:
            chunk_id = result['chunk'].get('chunkId')
            if chunk_id:
                if chunk_id in combined:
                    # Merge scores
                    combined[chunk_id]['graph_score'] = result.get('graph_score', 0)
                else:
                    combined[chunk_id] = {
                        **result,
                        'vector_score': 0,
                        'graph_score': result.get('graph_score', 0)
                    }
        
        # Calculate hybrid score
        for chunk_id, result in combined.items():
            vector_score = result.get('vector_score', 0)
            graph_score = result.get('graph_score', 0)
            
            # Normalize scores (vector scores are typically 0-1, graph scores need normalization)
            normalized_vector = vector_score
            normalized_graph = min(graph_score, 1.0)
            
            # Hybrid score: weighted combination
            hybrid_score = (1 - self.alpha) * normalized_graph + self.alpha * normalized_vector
            result['hybrid_score'] = hybrid_score
        
        # Sort by hybrid score
        sorted_results = sorted(
            combined.values(),
            key=lambda x: x['hybrid_score'],
            reverse=True
        )
        
        return sorted_results[:top_k]
    
    def _manual_vector_search(self,
                              query_embedding: List[float],
                              top_k: int,
                              filter_clause_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Manual vector similarity search using cosine similarity
        Fallback when vector index is not available
        """
        import numpy as np
        
        with self.driver.session() as session:
            # Get all chunks with embeddings
            if filter_clause_type:
                query = """
                    MATCH (c:PolicyClause)-[:HAS_PARAGRAPH]->(p:ParagraphChunk)
                    WHERE c.clauseType = $clause_type
                      AND p.embedding IS NOT NULL
                    RETURN p, c
                """
                result = session.run(query, clause_type=filter_clause_type)
            else:
                query = """
                    MATCH (c:PolicyClause)-[:HAS_PARAGRAPH]->(p:ParagraphChunk)
                    WHERE p.embedding IS NOT NULL
                    RETURN p, c
                """
                result = session.run(query)
            
            # Calculate cosine similarity manually
            results = []
            query_vec = np.array(query_embedding)
            
            for record in result:
                chunk = dict(record['p'])
                clause = dict(record['c'])
                
                if 'embedding' in chunk and chunk['embedding']:
                    chunk_vec = np.array(chunk['embedding'])
                    
                    # Cosine similarity
                    similarity = np.dot(query_vec, chunk_vec) / (
                        np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec)
                    )
                    
                    results.append({
                        'chunk': chunk,
                        'vector_score': float(similarity),
                        'clause': clause,
                        'source': 'vector_manual'
                    })
            
            # Sort by score and return top_k
            results.sort(key=lambda x: x['vector_score'], reverse=True)
            results = results[:top_k]
            
            logger.debug(f"Manual vector search returned {len(results)} results")
            return results
    
    def retrieve_product_overview(self, query: str) -> List[Dict[str, Any]]:
        """
        Retrieve product-level information using HyDE (Hypothetical Document Embeddings)
        
        Searches InsuranceProduct summary and HypotheticalQuestion nodes
        
        Args:
            query: User query about the product
            
        Returns:
            List with product summary and matching HyDE questions
        """
        # Generate query embedding
        query_embedding = self._generate_embedding(query)
        
        results = []
        
        with self.driver.session() as session:
            try:
                # Search HypotheticalQuestion nodes (HyDE)
                hyde_query = """
                    WITH $query_embedding AS queryVec
                    MATCH (prod:InsuranceProduct)-[:HAS_HYPOTHETICAL_QUESTION]->(hq:HypotheticalQuestion)
                    WITH hq, prod,
                         reduce(dot = 0.0, i IN range(0, size(queryVec)-1) | 
                            dot + queryVec[i] * hq.embedding[i]) AS dotProduct,
                         sqrt(reduce(sum = 0.0, i IN range(0, size(queryVec)-1) | 
                            sum + queryVec[i] * queryVec[i])) AS queryMag,
                         sqrt(reduce(sum = 0.0, i IN range(0, size(hq.embedding)-1) | 
                            sum + hq.embedding[i] * hq.embedding[i])) AS docMag
                    WITH hq, prod, dotProduct / (queryMag * docMag) AS similarity
                    WHERE similarity > 0.7
                    RETURN hq.question as question, 
                           hq.questionId as question_id,
                           prod.code as product_code,
                           prod.name as product_name,
                           prod.summary as product_summary,
                           similarity
                    ORDER BY similarity DESC
                    LIMIT 3
                """
                
                hyde_results = session.run(
                    hyde_query,
                    query_embedding=query_embedding
                )
                
                hyde_matches = list(hyde_results)
                
                if hyde_matches:
                    # Found matching HyDE questions - return product info
                    top_match = hyde_matches[0]
                    
                    result = {
                        'type': 'product_overview',
                        'product': {
                            'code': top_match['product_code'],
                            'name': top_match['product_name'],
                            'summary': top_match['product_summary']
                        },
                        'matched_questions': [
                            {
                                'question': m['question'],
                                'similarity': float(m['similarity'])
                            }
                            for m in hyde_matches
                        ],
                        'hybrid_score': float(hyde_matches[0]['similarity'])
                    }
                    
                    results.append(result)
                    logger.info(f"Found {len(hyde_matches)} matching HyDE questions")
                else:
                    # Fallback: Direct product summary search
                    logger.info("No HyDE matches, using product summary directly")
                    
                    product_query = """
                        MATCH (prod:InsuranceProduct)
                        RETURN prod.code as code,
                               prod.name as name,
                               prod.summary as summary
                        LIMIT 1
                    """
                    
                    prod_result = session.run(product_query)
                    prod_record = prod_result.single()
                    
                    if prod_record:
                        result = {
                            'type': 'product_overview',
                            'product': {
                                'code': prod_record['code'],
                                'name': prod_record['name'],
                                'summary': prod_record['summary']
                            },
                            'matched_questions': [],
                            'hybrid_score': 0.8
                        }
                        results.append(result)
                
            except Exception as e:
                logger.error(f"Error in product overview retrieval: {e}")
                import traceback
                traceback.print_exc()
        
        return results
    
    def close(self):
        """Close the driver connection"""
        self.driver.close()
        logger.info("HybridRetriever connection closed")


if __name__ == "__main__":
    # Example usage
    retriever = HybridRetriever(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
        alpha=settings.hybrid_alpha
    )
    
    # Test retrieval
    results = retriever.retrieve(
        query="화재로 인한 손해를 보상받을 수 있나요?",
        top_k=5,
        intent="coverage"
    )
    
    print(f"Retrieved {len(results)} results:")
    for i, result in enumerate(results):
        print(f"{i+1}. Score: {result['hybrid_score']:.3f}")
        print(f"   Text: {result['chunk']['text'][:100]}...")
    
    retriever.close()
