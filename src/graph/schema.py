"""
Neo4j Graph Schema for Insurance Policy Domain
Based on FIBO/FIB-DM style ontology
"""
from typing import List, Dict, Any
from neo4j import GraphDatabase
from loguru import logger


class PolicyGraphSchema:
    """
    Defines and manages the Neo4j graph schema for insurance policies
    """
    
    CONSTRAINTS = [
        # Unique constraints
        """
        CREATE CONSTRAINT policy_number_unique IF NOT EXISTS
        FOR (p:InsurancePolicy)
        REQUIRE p.policyNumber IS UNIQUE
        """,
        """
        CREATE CONSTRAINT product_code_unique IF NOT EXISTS
        FOR (pr:InsuranceProduct)
        REQUIRE pr.code IS UNIQUE
        """,
        """
        CREATE CONSTRAINT version_id_unique IF NOT EXISTS
        FOR (v:PolicyVersion)
        REQUIRE v.versionId IS UNIQUE
        """,
        """
        CREATE CONSTRAINT clause_id_unique IF NOT EXISTS
        FOR (c:PolicyClause)
        REQUIRE c.clauseId IS UNIQUE
        """,
    ]
    
    INDEXES = [
        # Text indexes for search
        """
        CREATE TEXT INDEX clause_text_index IF NOT EXISTS
        FOR (c:PolicyClause)
        ON (c.text)
        """,
        """
        CREATE TEXT INDEX clause_title_index IF NOT EXISTS
        FOR (c:PolicyClause)
        ON (c.title)
        """,
        # Property indexes
        """
        CREATE INDEX coverage_code_index IF NOT EXISTS
        FOR (c:Coverage)
        ON (c.code)
        """,
        """
        CREATE INDEX risk_type_name_index IF NOT EXISTS
        FOR (r:RiskType)
        ON (r.name)
        """,
    ]
    
    VECTOR_INDEX_TEMPLATE = """
    CREATE VECTOR INDEX {index_name} IF NOT EXISTS
    FOR (n:{node_label})
    ON (n.{property_name})
    OPTIONS {{
        indexConfig: {{
            `vector.dimensions`: {dimensions},
            `vector.similarity_function`: '{similarity_function}'
        }}
    }}
    """
    
    def __init__(self, uri: str, username: str, password: str):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        logger.info(f"Connected to Neo4j at {uri}")
    
    def close(self):
        """Close the Neo4j driver"""
        self.driver.close()
        logger.info("Neo4j connection closed")
    
    def initialize_schema(self, vector_dimensions: int = 1536, 
                         similarity_function: str = "cosine"):
        """
        Initialize the complete graph schema with constraints, indexes, and vector indexes
        """
        logger.info("Initializing Neo4j schema...")
        
        with self.driver.session() as session:
            # Create constraints
            for constraint in self.CONSTRAINTS:
                try:
                    session.run(constraint)
                    logger.debug(f"Created constraint: {constraint[:50]}...")
                except Exception as e:
                    logger.warning(f"Constraint creation warning: {e}")
            
            # Create indexes
            for index in self.INDEXES:
                try:
                    session.run(index)
                    logger.debug(f"Created index: {index[:50]}...")
                except Exception as e:
                    logger.warning(f"Index creation warning: {e}")
            
            # Create vector index for PolicyClause embeddings
            vector_index_query = self.VECTOR_INDEX_TEMPLATE.format(
                index_name="clause_embedding_index",
                node_label="PolicyClause",
                property_name="embedding",
                dimensions=vector_dimensions,
                similarity_function=similarity_function
            )
            
            try:
                session.run(vector_index_query)
                logger.info(f"Created vector index with {vector_dimensions} dimensions")
            except Exception as e:
                logger.warning(f"Vector index creation warning: {e}")
            
            # Create vector index for ParagraphChunk embeddings
            paragraph_vector_index = self.VECTOR_INDEX_TEMPLATE.format(
                index_name="paragraph_embedding_index",
                node_label="ParagraphChunk",
                property_name="embedding",
                dimensions=vector_dimensions,
                similarity_function=similarity_function
            )
            
            try:
                session.run(paragraph_vector_index)
                logger.info("Created paragraph chunk vector index")
            except Exception as e:
                logger.warning(f"Paragraph vector index warning: {e}")
        
        logger.info("✅ Schema initialization complete")
    
    def create_sample_data(self):
        """
        Create sample insurance policy data for testing
        """
        logger.info("Creating sample data...")
        
        sample_data_queries = [
            # Create Insurance Product
            """
            MERGE (prod:InsuranceProduct {
                code: 'LIG_HOME_FIRE_2025',
                name: 'LIG 주택화재보험',
                kind: 'property',
                lineOfBusiness: 'personal'
            })
            RETURN prod
            """,
            
            # Create Policy Version
            """
            MATCH (prod:InsuranceProduct {code: 'LIG_HOME_FIRE_2025'})
            MERGE (ver:PolicyVersion {
                versionId: 'LIG_HOME_FIRE_2025_V1',
                effectiveFrom: date('2025-01-01'),
                documentUrl: '/data/raw/LIG_주택화재보험약관.pdf'
            })
            MERGE (prod)-[:HAS_POLICY_VERSION]->(ver)
            RETURN ver
            """,
            
            # Create Sample Clause - 보상하는 손해
            """
            MATCH (ver:PolicyVersion {versionId: 'LIG_HOME_FIRE_2025_V1'})
            MERGE (c1:PolicyClause {
                clauseId: '제11조',
                title: '보상하는 손해',
                clauseType: 'Coverage',
                text: '회사는 이 계약에 따라 보험의 목적에 대하여 다음 각호의 손해를 보상합니다. 1. 직접손해 2. 소방손해 3. 피난손해',
                sectionPath: '제11조',
                articleNumber: 11
            })
            MERGE (ver)-[:HAS_CLAUSE]->(c1)
            RETURN c1
            """,
            
            # Create Coverage node
            """
            MATCH (c:PolicyClause {clauseId: '제11조'})
            MERGE (cov:Coverage {
                code: 'COV_FIRE_DIRECT',
                name: '화재 직접손해 담보'
            })
            MERGE (c)-[:DEFINES_COVERAGE]->(cov)
            RETURN cov
            """,
            
            # Create RiskType
            """
            MATCH (cov:Coverage {code: 'COV_FIRE_DIRECT'})
            MERGE (risk:RiskType {
                name: '화재',
                code: 'RISK_FIRE',
                category: 'property'
            })
            MERGE (cov)-[:COVERS_RISK]->(risk)
            RETURN risk
            """,
            
            # Create Special Clause (특약)
            """
            MATCH (ver:PolicyVersion {versionId: 'LIG_HOME_FIRE_2025_V1'})
            MERGE (rider:SpecialClause {
                code: 'RIDER_THEFT',
                name: '도난위험 특별약관',
                type: 'rider'
            })
            MERGE (ver)-[:HAS_SPECIAL_CLAUSE]->(rider)
            RETURN rider
            """,
            
            # Create rider clause
            """
            MATCH (rider:SpecialClause {code: 'RIDER_THEFT'})
            MERGE (c2:PolicyClause {
                clauseId: '도난위험특약_제2조',
                title: '보상하지 아니하는 손해',
                clauseType: 'Exclusion',
                text: '회사는 다음의 손해는 보상하지 아니합니다. 1. 계약자, 피보험자 또는 이들의 법정대리인의 고의 또는 중대한 과실로 생긴 손해',
                sectionPath: '도난위험특약>제2조'
            })
            MERGE (rider)-[:HAS_CLAUSE]->(c2)
            RETURN c2
            """,
        ]
        
        with self.driver.session() as session:
            for query in sample_data_queries:
                try:
                    result = session.run(query)
                    logger.debug(f"Executed: {query[:50]}...")
                except Exception as e:
                    logger.error(f"Error creating sample data: {e}")
        
        logger.info("✅ Sample data created")
    
    def verify_schema(self) -> Dict[str, Any]:
        """
        Verify that the schema is properly set up
        """
        logger.info("Verifying schema...")
        
        with self.driver.session() as session:
            # Count constraints
            constraints_result = session.run("SHOW CONSTRAINTS")
            constraints = list(constraints_result)
            
            # Count indexes
            indexes_result = session.run("SHOW INDEXES")
            indexes = list(indexes_result)
            
            # Count nodes by label
            node_counts = {}
            labels = ['InsuranceProduct', 'PolicyVersion', 'PolicyClause', 
                     'Coverage', 'Exclusion', 'RiskType', 'SpecialClause']
            
            for label in labels:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                node_counts[label] = result.single()['count']
        
        verification_result = {
            'constraints_count': len(constraints),
            'indexes_count': len(indexes),
            'node_counts': node_counts,
            'status': 'success'
        }
        
        logger.info(f"Schema verification: {verification_result}")
        return verification_result
    
    def clear_all_data(self):
        """
        ⚠️  WARNING: This deletes all nodes and relationships
        Use only for testing/development
        """
        logger.warning("🔥 CLEARING ALL DATA FROM NEO4J...")
        
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        logger.warning("✅ All data cleared")


if __name__ == "__main__":
    # Example usage
    from src.config import settings
    
    schema = PolicyGraphSchema(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password
    )
    
    # Initialize schema
    schema.initialize_schema(
        vector_dimensions=settings.vector_dimensions,
        similarity_function=settings.similarity_function
    )
    
    # Create sample data
    schema.create_sample_data()
    
    # Verify
    result = schema.verify_schema()
    print(result)
    
    schema.close()

