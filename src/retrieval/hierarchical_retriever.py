"""
Hierarchical Graph Retriever for Insurance Policy QA

Strategy:
1. Vector search to find top-k relevant nodes (Article/Paragraph/Item)
2. Traverse up to parent Articles for each node
3. LLM selects the most relevant Article (조항)
4. Collect all content from selected Article and its REFERS_TO connections
5. Build context avoiding duplication (child content already in parent)
"""
from typing import List, Dict, Any, Set, Tuple
from neo4j import GraphDatabase
from loguru import logger
from openai import OpenAI

from src.config.settings import settings


class HierarchicalRetriever:
    """
    Retriever that uses hierarchical structure and cross-references
    """
    
    def __init__(self, driver: GraphDatabase.driver):
        """
        Initialize retriever
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        
    def retrieve(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        Retrieve relevant context for query using hierarchical strategy
        
        Args:
            query: User query
            top_k: Number of initial candidates to retrieve
            
        Returns:
            Dictionary with selected article, context, and metadata
        """
        logger.info(f"🔍 Hierarchical retrieval for: {query}")
        
        # Step 1: Vector search for top-k nodes
        query_embedding = self._generate_embedding(query)
        candidate_nodes = self._vector_search(query_embedding, top_k)
        
        if not candidate_nodes:
            logger.warning("No candidate nodes found")
            return {
                'selected_article': None,
                'context': '',
                'sources': [],
                'metadata': {'error': 'No relevant nodes found'}
            }
        
        logger.info(f"  Found {len(candidate_nodes)} candidate nodes")
        
        # Step 2: Get parent Articles for each candidate
        articles = self._get_parent_articles(candidate_nodes)
        
        if not articles:
            logger.warning("No parent articles found")
            return {
                'selected_article': None,
                'context': '',
                'sources': [],
                'metadata': {'error': 'No parent articles found'}
            }
        
        logger.info(f"  Found {len(articles)} unique articles")
        
        # Step 3: LLM selects most relevant Article
        selected_article = self._select_best_article(query, articles)
        
        if not selected_article:
            logger.warning("No article selected by LLM")
            return {
                'selected_article': None,
                'context': '',
                'sources': [],
                'metadata': {'error': 'No article selected'}
            }
        
        logger.info(f"  ✅ Selected: {selected_article['articleId']} - {selected_article['title']}")
        
        # Step 4: Build context with REFERS_TO connections
        context_data = self._build_context_with_references(selected_article['articleId'])
        
        return {
            'selected_article': selected_article,
            'context': context_data['context'],
            'sources': context_data['sources'],
            'metadata': {
                'query': query,
                'top_k': top_k,
                'candidates_count': len(candidate_nodes),
                'articles_count': len(articles),
                'selected_article_id': selected_article['articleId'],
                'references_count': len(context_data['references'])
            }
        }
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        response = self.openai_client.embeddings.create(
            model=settings.embedding_model,
            input=text
        )
        return response.data[0].embedding
    
    def _vector_search(self, query_embedding: List[float], top_k: int) -> List[Dict[str, Any]]:
        """
        Vector search across Article, Paragraph, and Item nodes
        
        Returns list of nodes with their metadata and scores
        """
        with self.driver.session() as session:
            # Search across all node types with embeddings
            results = []
            
            # Search Articles
            try:
                article_results = session.run("""
                    MATCH (a:Article)
                    WHERE a.embedding IS NOT NULL
                    WITH a, 
                         reduce(dot = 0.0, i IN range(0, size(a.embedding)-1) | 
                             dot + a.embedding[i] * $query_embedding[i]) AS similarity
                    RETURN 'Article' AS node_type,
                           a.articleId AS node_id,
                           a.title AS title,
                           a.text AS text,
                           similarity
                    ORDER BY similarity DESC
                    LIMIT $top_k
                    """, query_embedding=query_embedding, top_k=top_k)
                
                for record in article_results:
                    results.append({
                        'node_type': record['node_type'],
                        'node_id': record['node_id'],
                        'title': record['title'],
                        'text': record['text'],
                        'similarity': record['similarity']
                    })
            except Exception as e:
                logger.warning(f"Article vector search failed: {e}")
            
            # Search Paragraphs
            try:
                para_results = session.run("""
                    MATCH (p:Paragraph)
                    WHERE p.embedding IS NOT NULL
                    WITH p, 
                         reduce(dot = 0.0, i IN range(0, size(p.embedding)-1) | 
                             dot + p.embedding[i] * $query_embedding[i]) AS similarity
                    RETURN 'Paragraph' AS node_type,
                           p.paragraphId AS node_id,
                           p.text AS text,
                           similarity
                    ORDER BY similarity DESC
                    LIMIT $top_k
                    """, query_embedding=query_embedding, top_k=top_k)
                
                for record in para_results:
                    results.append({
                        'node_type': record['node_type'],
                        'node_id': record['node_id'],
                        'text': record['text'],
                        'similarity': record['similarity']
                    })
            except Exception as e:
                logger.warning(f"Paragraph vector search failed: {e}")
            
            # Search Items
            try:
                item_results = session.run("""
                    MATCH (i:Item)
                    WHERE i.embedding IS NOT NULL
                    WITH i, 
                         reduce(dot = 0.0, i IN range(0, size(i.embedding)-1) | 
                             dot + i.embedding[i] * $query_embedding[i]) AS similarity
                    RETURN 'Item' AS node_type,
                           i.itemId AS node_id,
                           i.text AS text,
                           similarity
                    ORDER BY similarity DESC
                    LIMIT $top_k
                    """, query_embedding=query_embedding, top_k=top_k)
                
                for record in item_results:
                    results.append({
                        'node_type': record['node_type'],
                        'node_id': record['node_id'],
                        'text': record['text'],
                        'similarity': record['similarity']
                    })
            except Exception as e:
                logger.warning(f"Item vector search failed: {e}")
            
            # Sort all results by similarity
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
            return results[:top_k]
    
    def _get_parent_articles(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Get parent Article for each node
        
        Returns unique list of Articles with their metadata
        """
        articles = {}
        
        with self.driver.session() as session:
            for node in nodes:
                node_type = node['node_type']
                node_id = node['node_id']
                
                if node_type == 'Article':
                    # Already an Article
                    article_id = node_id
                    title = node.get('title', '')
                    text = node.get('text', '')
                elif node_type == 'Paragraph':
                    # Get parent Article through Paragraph
                    result = session.run("""
                        MATCH (a:Article)-[:HAS_PARAGRAPH]->(p:Paragraph {paragraphId: $para_id})
                        RETURN a.articleId AS articleId, a.title AS title, a.text AS text
                        """, para_id=node_id)
                    record = result.single()
                    if record:
                        article_id = record['articleId']
                        title = record['title']
                        text = record['text']
                    else:
                        continue
                elif node_type == 'Item':
                    # Get parent Article through Paragraph <- Item
                    result = session.run("""
                        MATCH (a:Article)-[:HAS_PARAGRAPH]->(p:Paragraph)-[:HAS_ITEM]->(i:Item {itemId: $item_id})
                        RETURN a.articleId AS articleId, a.title AS title, a.text AS text
                        """, item_id=node_id)
                    record = result.single()
                    if record:
                        article_id = record['articleId']
                        title = record['title']
                        text = record['text']
                    else:
                        continue
                else:
                    continue
                
                # Add to unique articles dict
                if article_id not in articles:
                    articles[article_id] = {
                        'articleId': article_id,
                        'title': title,
                        'text': text,
                        'source_nodes': []
                    }
                
                articles[article_id]['source_nodes'].append({
                    'node_type': node_type,
                    'node_id': node_id,
                    'similarity': node['similarity']
                })
        
        return list(articles.values())
    
    def _select_best_article(self, query: str, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Use LLM to select the most relevant Article
        
        Returns the selected Article dictionary
        """
        # Prepare article summaries for LLM
        article_summaries = []
        for i, article in enumerate(articles):
            summary = f"{i+1}. {article['articleId']} - {article['title']}\n"
            summary += f"   내용: {article['text'][:200]}..."
            article_summaries.append(summary)
        
        articles_text = "\n\n".join(article_summaries)
        
        # LLM prompt
        prompt = f"""다음은 사용자 질의와 관련 가능성이 있는 보험약관 조항들입니다.

사용자 질의: {query}

후보 조항들:
{articles_text}

위 조항들 중에서 사용자 질의에 가장 적합하고 관련성이 높은 조항을 **단 하나만** 선택해주세요.

응답 형식 (JSON):
{{
  "selected_index": 1,
  "reason": "선택 이유를 한 문장으로"
}}
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "당신은 보험약관 전문가입니다. 주어진 조항들 중 질의에 가장 적합한 조항을 선택합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            selected_index = result['selected_index'] - 1  # Convert to 0-based
            reason = result['reason']
            
            if 0 <= selected_index < len(articles):
                selected = articles[selected_index]
                logger.info(f"  LLM 선택: {selected['articleId']} - 이유: {reason}")
                return selected
            else:
                logger.warning(f"Invalid index {selected_index}, returning first article")
                return articles[0]
                
        except Exception as e:
            logger.error(f"LLM selection failed: {e}, returning first article")
            return articles[0]
    
    def _build_context_with_references(self, article_id: str) -> Dict[str, Any]:
        """
        Build context from selected Article and all REFERS_TO connections
        
        Avoids duplication: if child content is in parent, use only parent
        
        Returns:
            - context: assembled text
            - sources: list of source nodes
            - references: list of referenced nodes
        """
        context_parts = []
        sources = []
        references = []
        seen_nodes = set()
        
        with self.driver.session() as session:
            # Get main Article and all its Paragraphs/Items
            result = session.run("""
                MATCH (a:Article {articleId: $article_id})
                OPTIONAL MATCH (a)-[:HAS_PARAGRAPH]->(p:Paragraph)
                OPTIONAL MATCH (p)-[:HAS_ITEM]->(i:Item)
                RETURN a.articleId AS articleId, a.title AS title, a.text AS fullText,
                       collect(DISTINCT {id: p.paragraphId, text: p.text, type: 'Paragraph'}) AS paragraphs,
                       collect(DISTINCT {id: i.itemId, text: i.text, type: 'Item'}) AS items
                """, article_id=article_id)
            
            record = result.single()
            if not record:
                return {'context': '', 'sources': [], 'references': []}
            
            # Add main Article
            main_article = f"# {record['articleId']}: {record['title']}\n\n{record['fullText']}\n\n"
            context_parts.append(main_article)
            sources.append({
                'type': 'Article',
                'id': record['articleId'],
                'title': record['title']
            })
            seen_nodes.add(record['articleId'])
            
            # Find all REFERS_TO connections from Paragraphs in this Article
            ref_from_paragraphs = session.run("""
                MATCH (a:Article {articleId: $article_id})-[:HAS_PARAGRAPH]->(p:Paragraph)-[:REFERS_TO]->(ref)
                RETURN DISTINCT labels(ref)[0] AS ref_type,
                       CASE 
                         WHEN ref.articleId IS NOT NULL THEN ref.articleId
                         WHEN ref.paragraphId IS NOT NULL THEN ref.paragraphId
                         ELSE ref.itemId
                       END AS ref_id,
                       CASE 
                         WHEN ref.title IS NOT NULL THEN ref.title
                         ELSE ''
                       END AS ref_title,
                       CASE 
                         WHEN ref.text IS NOT NULL THEN ref.text
                         ELSE ''
                       END AS ref_text
                """, article_id=article_id)
            
            # Add referenced nodes from paragraphs
            for ref_record in ref_from_paragraphs:
                ref_id = ref_record['ref_id']
                if ref_id and ref_id not in seen_nodes:
                    ref_type = ref_record['ref_type']
                    ref_title = ref_record['ref_title']
                    ref_text = ref_record['ref_text']
                    
                    # Format reference based on type
                    if ref_type == 'Article':
                        ref_context = f"## [참조] {ref_id}: {ref_title}\n\n{ref_text}\n\n"
                    elif ref_type == 'Paragraph':
                        ref_context = f"## [참조] {ref_id}\n\n{ref_text}\n\n"
                    elif ref_type == 'Item':
                        ref_context = f"## [참조] {ref_id}\n\n{ref_text}\n\n"
                    else:
                        continue
                    
                    context_parts.append(ref_context)
                    references.append({
                        'type': ref_type,
                        'id': ref_id,
                        'title': ref_title if ref_title else ''
                    })
                    seen_nodes.add(ref_id)
            
            # Find all REFERS_TO connections from Items in this Article
            ref_from_items = session.run("""
                MATCH (a:Article {articleId: $article_id})-[:HAS_PARAGRAPH]->(:Paragraph)-[:HAS_ITEM]->(i:Item)-[:REFERS_TO]->(ref)
                RETURN DISTINCT labels(ref)[0] AS ref_type,
                       CASE 
                         WHEN ref.articleId IS NOT NULL THEN ref.articleId
                         WHEN ref.paragraphId IS NOT NULL THEN ref.paragraphId
                         ELSE ref.itemId
                       END AS ref_id,
                       CASE 
                         WHEN ref.title IS NOT NULL THEN ref.title
                         ELSE ''
                       END AS ref_title,
                       CASE 
                         WHEN ref.text IS NOT NULL THEN ref.text
                         ELSE ''
                       END AS ref_text
                """, article_id=article_id)
            
            # Add referenced nodes from items
            for ref_record in ref_from_items:
                ref_id = ref_record['ref_id']
                if ref_id and ref_id not in seen_nodes:
                    ref_type = ref_record['ref_type']
                    ref_title = ref_record['ref_title']
                    ref_text = ref_record['ref_text']
                    
                    # Format reference based on type
                    if ref_type == 'Article':
                        ref_context = f"## [참조] {ref_id}: {ref_title}\n\n{ref_text}\n\n"
                    elif ref_type == 'Paragraph':
                        ref_context = f"## [참조] {ref_id}\n\n{ref_text}\n\n"
                    elif ref_type == 'Item':
                        ref_context = f"## [참조] {ref_id}\n\n{ref_text}\n\n"
                    else:
                        continue
                    
                    context_parts.append(ref_context)
                    references.append({
                        'type': ref_type,
                        'id': ref_id,
                        'title': ref_title if ref_title else ''
                    })
                    seen_nodes.add(ref_id)
        
        context = "".join(context_parts)
        
        return {
            'context': context,
            'sources': sources,
            'references': references
        }


