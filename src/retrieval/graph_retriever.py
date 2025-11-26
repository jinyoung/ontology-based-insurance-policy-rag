"""
Graph-based Retriever for Insurance Policy Knowledge Graph
Retrieves relevant nodes using Cypher queries
"""
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
from loguru import logger


class GraphRetriever:
    """
    Retrieves relevant policy information from Neo4j graph
    using structure-aware queries
    """
    
    def __init__(self, uri: str, username: str, password: str):
        """
        Initialize graph retriever
        
        Args:
            uri: Neo4j URI
            username: Neo4j username
            password: Neo4j password
        """
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        logger.info(f"GraphRetriever connected to {uri}")
    
    def retrieve_by_clause_id(self, clause_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific clause and its related nodes
        
        Args:
            clause_id: Clause identifier (e.g., "제11조")
            
        Returns:
            Dictionary with clause data and relationships
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:PolicyClause {clauseId: $clause_id})
                OPTIONAL MATCH (c)-[:DEFINES_COVERAGE]->(cov:Coverage)
                OPTIONAL MATCH (c)-[:HAS_EXCLUSION]->(exc:Exclusion)
                OPTIONAL MATCH (c)-[:HAS_PARAGRAPH]->(p:ParagraphChunk)
                RETURN c,
                       collect(DISTINCT cov) as coverages,
                       collect(DISTINCT exc) as exclusions,
                       collect(DISTINCT p) as paragraphs
                """,
                clause_id=clause_id
            )
            
            record = result.single()
            if not record:
                return {}
            
            return {
                'clause': dict(record['c']),
                'coverages': [dict(c) for c in record['coverages'] if c],
                'exclusions': [dict(e) for e in record['exclusions'] if e],
                'paragraphs': [dict(p) for p in record['paragraphs'] if p]
            }
    
    def retrieve_by_coverage_keyword(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find clauses related to coverage using keyword search
        
        Args:
            keyword: Search keyword (e.g., "화재", "도난")
            limit: Maximum results
            
        Returns:
            List of matching clauses
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:PolicyClause)
                WHERE c.clauseType = 'Coverage'
                  AND (c.text CONTAINS $keyword OR c.title CONTAINS $keyword)
                OPTIONAL MATCH (c)-[:DEFINES_COVERAGE]->(cov:Coverage)
                RETURN c, collect(DISTINCT cov) as coverages
                LIMIT $limit
                """,
                keyword=keyword,
                limit=limit
            )
            
            clauses = []
            for record in result:
                clauses.append({
                    'clause': dict(record['c']),
                    'coverages': [dict(c) for c in record['coverages'] if c]
                })
            
            return clauses
    
    def retrieve_by_exclusion_keyword(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find clauses related to exclusions using keyword search
        
        Args:
            keyword: Search keyword
            limit: Maximum results
            
        Returns:
            List of matching clauses
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:PolicyClause)
                WHERE c.clauseType = 'Exclusion'
                  AND (c.text CONTAINS $keyword OR c.title CONTAINS $keyword)
                OPTIONAL MATCH (c)-[:HAS_EXCLUSION]->(exc:Exclusion)
                RETURN c, collect(DISTINCT exc) as exclusions
                LIMIT $limit
                """,
                keyword=keyword,
                limit=limit
            )
            
            clauses = []
            for record in result:
                clauses.append({
                    'clause': dict(record['c']),
                    'exclusions': [dict(e) for e in record['exclusions'] if e]
                })
            
            return clauses
    
    def retrieve_by_special_clause(self, special_clause_name: str) -> List[Dict[str, Any]]:
        """
        Retrieve all clauses under a special clause (특약)
        
        Args:
            special_clause_name: Name of special clause
            
        Returns:
            List of clauses in that special clause
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (sc:SpecialClause {name: $name})-[:HAS_CLAUSE]->(c:PolicyClause)
                RETURN c
                ORDER BY c.articleNumber
                """,
                name=special_clause_name
            )
            
            return [{'clause': dict(record['c'])} for record in result]
    
    def retrieve_neighborhood(self, clause_id: str, depth: int = 2) -> Dict[str, Any]:
        """
        Retrieve multi-hop neighborhood around a clause
        
        Args:
            clause_id: Starting clause ID
            depth: Number of hops
            
        Returns:
            Neighborhood graph data
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH path = (c:PolicyClause {clauseId: $clause_id})-[*1..$depth]-(n)
                RETURN path
                LIMIT 100
                """,
                clause_id=clause_id,
                depth=depth
            )
            
            nodes = []
            relationships = []
            
            for record in result:
                path = record['path']
                for node in path.nodes:
                    node_dict = dict(node)
                    node_dict['labels'] = list(node.labels)
                    if node_dict not in nodes:
                        nodes.append(node_dict)
                
                for rel in path.relationships:
                    relationships.append({
                        'type': rel.type,
                        'start': dict(rel.start_node),
                        'end': dict(rel.end_node)
                    })
            
            return {
                'nodes': nodes,
                'relationships': relationships
            }
    
    def retrieve_by_version(self, version_id: str) -> Dict[str, Any]:
        """
        Retrieve all data for a policy version
        
        Args:
            version_id: Policy version ID
            
        Returns:
            Complete policy version data
        """
        with self.driver.session() as session:
            # Get version info
            version_result = session.run("""
                MATCH (ver:PolicyVersion {versionId: $version_id})
                OPTIONAL MATCH (prod:InsuranceProduct)-[:HAS_POLICY_VERSION]->(ver)
                RETURN ver, prod
                """,
                version_id=version_id
            )
            
            version_record = version_result.single()
            if not version_record:
                return {}
            
            # Get all clauses
            clauses_result = session.run("""
                MATCH (ver:PolicyVersion {versionId: $version_id})-[:HAS_CLAUSE]->(c:PolicyClause)
                RETURN c
                ORDER BY c.articleNumber
                """,
                version_id=version_id
            )
            
            clauses = [dict(record['c']) for record in clauses_result]
            
            # Get special clauses
            special_result = session.run("""
                MATCH (ver:PolicyVersion {versionId: $version_id})-[:HAS_SPECIAL_CLAUSE]->(sc:SpecialClause)
                RETURN sc
                """,
                version_id=version_id
            )
            
            special_clauses = [dict(record['sc']) for record in special_result]
            
            return {
                'version': dict(version_record['ver']),
                'product': dict(version_record['prod']) if version_record['prod'] else None,
                'clauses': clauses,
                'special_clauses': special_clauses
            }
    
    def close(self):
        """Close the driver connection"""
        self.driver.close()
        logger.info("GraphRetriever connection closed")


if __name__ == "__main__":
    # Example usage
    from src.config.settings import settings
    
    retriever = GraphRetriever(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password
    )
    
    # Test retrieval
    result = retriever.retrieve_by_coverage_keyword("화재")
    print(f"Found {len(result)} coverage clauses")
    
    retriever.close()
