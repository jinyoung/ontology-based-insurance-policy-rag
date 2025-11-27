"""
Rule-based Chunker for Insurance Policy Documents
Chunks based on structural rules (조/항/호)
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger
from src.parsers.clause_extractor import Clause


@dataclass
class RuleChunk:
    """Represents a rule-based chunk"""
    chunk_id: str
    chunk_type: str  # 'clause', 'item', 'table'
    content: str
    metadata: Dict[str, Any]
    clause_id: Optional[str] = None
    parent_id: Optional[str] = None


class RuleBasedChunker:
    """
    Rule-based chunker that preserves the hierarchical structure
    of insurance policy documents (조/항/호)
    """
    
    def __init__(self, max_chunk_size: int = 2000):
        """
        Initialize rule-based chunker
        
        Args:
            max_chunk_size: Maximum characters per chunk
        """
        self.max_chunk_size = max_chunk_size
        self.chunks: List[RuleChunk] = []
    
    def chunk_clauses(self, clauses: List[Clause]) -> List[RuleChunk]:
        """
        Create chunks from extracted clauses
        
        Args:
            clauses: List of extracted Clause objects
            
        Returns:
            List of RuleChunk objects
        """
        self.chunks = []
        
        for clause in clauses:
            # Check if clause is too large
            if len(clause.full_text) > self.max_chunk_size:
                # Split into sub-chunks based on items
                if clause.items and len(clause.items) > 0:
                    self._chunk_large_clause_by_items(clause)
                else:
                    # Split by paragraphs if no items
                    self._chunk_large_clause_by_paragraphs(clause)
            else:
                # Create single chunk for the entire clause
                chunk = RuleChunk(
                    chunk_id=f"{clause.clause_id}_full",
                    chunk_type="clause",
                    content=clause.full_text,
                    metadata={
                        'clause_id': clause.clause_id,
                        'article_number': clause.article_number,
                        'title': clause.title,
                        'clause_type': clause.clause_type,
                        'section_path': clause.section_path,
                        'parent_section': clause.parent_section,
                        'char_count': len(clause.full_text)
                    },
                    clause_id=clause.clause_id
                )
                self.chunks.append(chunk)
        
        logger.info(f"✅ Created {len(self.chunks)} rule-based chunks from {len(clauses)} clauses")
        return self.chunks
    
    def _chunk_large_clause_by_items(self, clause: Clause):
        """
        Split a large clause into multiple chunks based on items (호)
        
        Args:
            clause: Clause object to split
        """
        # Create header chunk with clause title and intro
        header_lines = []
        full_lines = clause.full_text.split('\n')
        
        for line in full_lines[:5]:  # Take first few lines as header
            if line.strip():
                header_lines.append(line)
            if len('\n'.join(header_lines)) > 200:
                break
        
        header_text = '\n'.join(header_lines)
        
        # Create header chunk
        header_chunk = RuleChunk(
            chunk_id=f"{clause.clause_id}_header",
            chunk_type="clause_header",
            content=header_text,
            metadata={
                'clause_id': clause.clause_id,
                'title': clause.title,
                'clause_type': clause.clause_type,
                'section_path': clause.section_path,
                'is_header': True
            },
            clause_id=clause.clause_id
        )
        self.chunks.append(header_chunk)
        
        # Create chunks for each item
        for idx, item in enumerate(clause.items):
            item_chunk = RuleChunk(
                chunk_id=f"{clause.clause_id}_item_{idx+1}",
                chunk_type="item",
                content=item,
                metadata={
                    'clause_id': clause.clause_id,
                    'title': clause.title,
                    'item_number': idx + 1,
                    'clause_type': clause.clause_type,
                    'section_path': f"{clause.section_path}>항{idx+1}"
                },
                clause_id=clause.clause_id,
                parent_id=f"{clause.clause_id}_header"
            )
            self.chunks.append(item_chunk)
        
        logger.debug(f"Split {clause.clause_id} into 1 header + {len(clause.items)} items")
    
    def _chunk_large_clause_by_paragraphs(self, clause: Clause):
        """
        Split a large clause by paragraphs when no items exist
        
        Args:
            clause: Clause object to split
        """
        paragraphs = [p.strip() for p in clause.full_text.split('\n\n') if p.strip()]
        
        current_chunk_text = []
        current_chunk_size = 0
        chunk_counter = 0
        
        for para in paragraphs:
            para_size = len(para)
            
            if current_chunk_size + para_size > self.max_chunk_size and current_chunk_text:
                # Save current chunk
                chunk = RuleChunk(
                    chunk_id=f"{clause.clause_id}_para_{chunk_counter}",
                    chunk_type="paragraph",
                    content='\n\n'.join(current_chunk_text),
                    metadata={
                        'clause_id': clause.clause_id,
                        'title': clause.title,
                        'clause_type': clause.clause_type,
                        'section_path': clause.section_path,
                        'paragraph_group': chunk_counter
                    },
                    clause_id=clause.clause_id
                )
                self.chunks.append(chunk)
                
                # Reset
                current_chunk_text = [para]
                current_chunk_size = para_size
                chunk_counter += 1
            else:
            current_chunk_text.append(para)
                current_chunk_size += para_size
        
        # Save last chunk
        if current_chunk_text:
            chunk = RuleChunk(
                chunk_id=f"{clause.clause_id}_para_{chunk_counter}",
                chunk_type="paragraph",
                content='\n\n'.join(current_chunk_text),
                metadata={
                    'clause_id': clause.clause_id,
                    'title': clause.title,
                    'clause_type': clause.clause_type,
                    'section_path': clause.section_path,
                    'paragraph_group': chunk_counter
                },
                clause_id=clause.clause_id
            )
            self.chunks.append(chunk)
        
        logger.debug(f"Split {clause.clause_id} into {chunk_counter + 1} paragraph chunks")
    
    def create_table_chunk(self, table_text: str, metadata: Dict[str, Any]) -> RuleChunk:
        """
        Create a chunk for a table
        
        Args:
            table_text: Table content
            metadata: Table metadata
            
        Returns:
            RuleChunk object
        """
        chunk = RuleChunk(
            chunk_id=metadata.get('table_id', 'table_unknown'),
            chunk_type="table",
            content=table_text,
            metadata=metadata
        )
        self.chunks.append(chunk)
        return chunk
    
    def get_chunks_by_clause(self, clause_id: str) -> List[RuleChunk]:
        """
        Get all chunks belonging to a specific clause
        
        Args:
            clause_id: Clause identifier
            
        Returns:
            List of chunks
        """
        return [c for c in self.chunks if c.clause_id == clause_id]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get chunking statistics
        
        Returns:
            Dictionary of statistics
        """
        stats = {
            'total_chunks': len(self.chunks),
            'chunks_by_type': {},
            'avg_chunk_size': 0,
            'max_chunk_size': 0,
            'min_chunk_size': float('inf')
        }
        
        chunk_sizes = []
        
        for chunk in self.chunks:
            # Count by type
            if chunk.chunk_type not in stats['chunks_by_type']:
                stats['chunks_by_type'][chunk.chunk_type] = 0
            stats['chunks_by_type'][chunk.chunk_type] += 1
            
            # Size stats
            size = len(chunk.content)
            chunk_sizes.append(size)
            stats['max_chunk_size'] = max(stats['max_chunk_size'], size)
            stats['min_chunk_size'] = min(stats['min_chunk_size'], size)
        
        if chunk_sizes:
            stats['avg_chunk_size'] = sum(chunk_sizes) / len(chunk_sizes)
        
        return stats
    
    def to_dict(self) -> List[Dict[str, Any]]:
        """
        Convert chunks to dictionary format
        
        Returns:
            List of chunk dictionaries
        """
        return [
            {
                'chunk_id': c.chunk_id,
                'chunk_type': c.chunk_type,
                'content': c.content,
                'metadata': c.metadata,
                'clause_id': c.clause_id,
                'parent_id': c.parent_id,
                'char_count': len(c.content)
            }
            for c in self.chunks
        ]


if __name__ == "__main__":
    # Example usage
    from src.parsers.clause_extractor import extract_clauses_from_text
    
    sample_text = """
    제11조(보상하는 손해) 회사는 이 계약에 따라 보험의 목적에 대하여 다음 각호의 손해를 보상합니다.
    1. 직접손해: 화재로 인한 직접적인 손해
    2. 소방손해: 소화 활동으로 인한 손해
    3. 피난손해: 피난 과정에서 발생한 손해
    
    제12조(보상하지 아니하는 손해) 회사는 다음의 경우 보상하지 않습니다.
    1. 계약자의 고의
    2. 전쟁, 혁명
    """
    
    clauses = extract_clauses_from_text(sample_text)
    chunker = RuleBasedChunker(max_chunk_size=500)
    chunks = chunker.chunk_clauses(clauses)
    
    print(f"\n✅ Created {len(chunks)} chunks")
    stats = chunker.get_statistics()
    print(f"Statistics: {stats}")
