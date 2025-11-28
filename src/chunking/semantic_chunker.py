"""
LLM-based Semantic Chunker for Insurance Policy Documents
Uses LLM to intelligently split complex clauses into semantic units
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger
from openai import OpenAI
import json
from src.config.settings import settings


@dataclass
class SemanticChunk:
    """Represents a semantically coherent chunk"""
    chunk_id: str
    content: str
    semantic_type: str  # coverage, exclusion, condition, definition, etc.
    metadata: Dict[str, Any]
    parent_chunk_id: Optional[str] = None


class SemanticChunker:
    """
    LLM-based semantic chunker that splits large clauses
    into meaningful semantic units while preserving context
    """
    
    SEMANTIC_SPLIT_PROMPT = """You are an expert at analyzing insurance policy documents in Korean.

Your task is to:
1. Carefully read the insurance policy clause
2. Identify the SEMANTIC TYPE of each distinct concept within the clause
3. Split into semantically coherent sub-units if needed

SEMANTIC TYPE DEFINITIONS:
- "coverage": What IS covered/compensated (보상하는 손해, 지급하는 보험금)
- "exclusion": What is NOT covered/excluded (보상하지 아니하는 손해, 면책사항)
- "condition": Requirements, procedures, obligations (조건, 의무, 청구절차)
- "deductible": Self-payment amounts (자기부담금)
- "limit": Coverage limits, maximum amounts (보상한도, 최고한도액)
- "definition": Term definitions (용어의 정의, 의미)
- "procedure": Administrative procedures (절차, 방법)
- "general": Other general provisions

CRITICAL RULES:
1. DO NOT summarize, paraphrase, or rewrite - preserve EXACT original text
2. DO NOT change any wording
3. Focus on ACCURATE semantic type identification
4. Split ONLY when there are clearly different semantic types within one clause
5. Each sub-unit should contain ONE semantic type

Example:
If a clause has "1. 보상하는 손해" and "2. 보상하지 아니하는 손해", 
split into two sub-units: one "coverage" and one "exclusion"

Clause to analyze:
---
Title: {title}
Hint (may be inaccurate): {clause_type}

Content:
{content}
---

Return a JSON object with a "chunks" array:
{{
  "chunks": [
    {{
      "label": "brief descriptive label (2-4 words in Korean)",
      "semantic_type": "coverage|exclusion|condition|deductible|limit|definition|procedure|general",
      "content": "exact text from original (DO NOT modify)",
      "reasoning": "brief reason for this classification"
    }}
  ]
}}

If the entire clause represents a single semantic type, return one chunk with all content.
"""
    
    def __init__(self, model: str = None):
        """
        Initialize semantic chunker
        
        Args:
            model: OpenAI model to use (default from settings)
        """
        self.model = model or settings.llm_model
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.chunks: List[SemanticChunk] = []
        logger.info(f"Initialized SemanticChunker with model: {self.model}")
    
    def chunk_text(self, text: str, metadata: Dict[str, Any]) -> List[SemanticChunk]:
        """
        Split text into semantic chunks using LLM
        
        Args:
            text: Text to chunk
            metadata: Metadata about the text (clause_id, title, type, etc.)
            
        Returns:
            List of SemanticChunk objects
        """
        # Skip if text is too short
        if len(text) < 150:
            chunk = SemanticChunk(
                chunk_id=f"{metadata.get('clause_id', 'chunk')}_semantic_0",
                content=text,
                semantic_type='general',  # Default for short texts
                metadata={
                    **metadata,
                    'llm_identified': False,
                    'reason': 'text_too_short'
                }
            )
            return [chunk]
        
        try:
            # Call LLM to split text and identify semantic types
            prompt = self.SEMANTIC_SPLIT_PROMPT.format(
                title=metadata.get('title', 'N/A'),
                clause_type=metadata.get('clause_type') or 'Unknown',
                content=text
            )
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert at analyzing Korean insurance policy documents. "
                                   "Your expertise is in identifying semantic types (coverage/exclusion/condition/etc). "
                                   "Always return valid JSON with accurate semantic_type classification."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            
            # Parse JSON response
            try:
                # Handle both array and object formats
                result = json.loads(result_text)
                if isinstance(result, dict) and 'chunks' in result:
                    sub_units = result['chunks']
                elif isinstance(result, dict) and 'sub_units' in result:
                    sub_units = result['sub_units']
                elif isinstance(result, list):
                    sub_units = result
                else:
                    # If unexpected format, treat whole text as single chunk
                    logger.warning(f"Unexpected JSON format from LLM. Using fallback.")
                    sub_units = [{
                        'label': metadata.get('title', 'content'),
                        'semantic_type': 'general',
                        'content': text,
                        'reasoning': 'fallback due to unexpected response format'
                    }]
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}. Using fallback.")
                sub_units = [{
                    'label': metadata.get('title', 'content'),
                    'semantic_type': 'general',
                    'content': text,
                    'reasoning': 'fallback due to JSON parse error'
                }]
            
            # Create SemanticChunk objects with LLM-identified types
            chunks = []
            base_id = metadata.get('clause_id', 'chunk')
            
            for idx, unit in enumerate(sub_units):
                semantic_type = unit.get('semantic_type', 'general')
                reasoning = unit.get('reasoning', '')
                
                chunk = SemanticChunk(
                    chunk_id=f"{base_id}_semantic_{idx}",
                    content=unit.get('content', '').strip(),
                    semantic_type=semantic_type,
                    metadata={
                        **metadata,
                        'label': unit.get('label', ''),
                        'reasoning': reasoning,
                        'chunk_index': idx,
                        'total_chunks': len(sub_units),
                        'llm_identified': True  # Mark that this was LLM-identified
                    },
                    parent_chunk_id=base_id
                )
                chunks.append(chunk)
            
            logger.debug(f"Split {base_id} into {len(chunks)} semantic chunks with LLM-identified types")
            return chunks
        
        except Exception as e:
            logger.error(f"Error in semantic chunking: {e}. Falling back to single chunk.")
            # Fallback: return original text as single chunk
            chunk = SemanticChunk(
                chunk_id=f"{metadata.get('clause_id', 'chunk')}_semantic_0",
                content=text,
                semantic_type='general',  # Default to general on error
            metadata={
                    **metadata,
                    'llm_identified': False,
                    'fallback_reason': str(e)
                }
            )
            return [chunk]
    
    # Removed _infer_type_from_metadata - semantic types should be determined by LLM only
    
    def chunk_multiple_texts(self, texts: List[Dict[str, Any]]) -> List[SemanticChunk]:
        """
        Chunk multiple texts in batch
        
        Args:
            texts: List of dicts with 'content' and 'metadata' keys
            
        Returns:
            List of all semantic chunks
        """
        all_chunks = []
        
        for item in texts:
            content = item.get('content', '')
            metadata = item.get('metadata', {})
            
            chunks = self.chunk_text(content, metadata)
                    all_chunks.extend(chunks)
                    
        self.chunks = all_chunks
        logger.info(f"✅ Created {len(all_chunks)} semantic chunks from {len(texts)} texts")
        
        return all_chunks
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get chunking statistics
            
        Returns:
            Dictionary of statistics
        """
        if not self.chunks:
            return {'total_chunks': 0}
        
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
            if chunk.semantic_type not in stats['chunks_by_type']:
                stats['chunks_by_type'][chunk.semantic_type] = 0
            stats['chunks_by_type'][chunk.semantic_type] += 1
            
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
                'content': c.content,
                'semantic_type': c.semantic_type,
                'metadata': c.metadata,
                'parent_chunk_id': c.parent_chunk_id,
                'char_count': len(c.content)
            }
            for c in self.chunks
        ]


class HybridChunker:
    """
    Combines rule-based and semantic chunking
    """
    
    def __init__(self, rule_chunker, semantic_chunker):
        """
        Initialize hybrid chunker
        
        Args:
            rule_chunker: RuleBasedChunker instance
            semantic_chunker: SemanticChunker instance
        """
        self.rule_chunker = rule_chunker
        self.semantic_chunker = semantic_chunker
        self.final_chunks = []
    
    def chunk(self, clauses: List[Any], apply_semantic: bool = True) -> List[Any]:
        """
        Apply hybrid chunking strategy
        
        Args:
            clauses: List of Clause objects
            apply_semantic: Whether to apply semantic chunking to large chunks
            
        Returns:
            List of final chunks
        """
        # First, apply rule-based chunking
        rule_chunks = self.rule_chunker.chunk_clauses(clauses)
        logger.info(f"Rule-based chunking: {len(rule_chunks)} chunks")
        
        if not apply_semantic:
            return rule_chunks
        
        # Then, apply semantic chunking to large chunks
        texts_to_refine = []
        
        for chunk in rule_chunks:
            # Apply semantic chunking if chunk is large (> 1000 chars)
            if len(chunk.content) > 1000 and chunk.chunk_type == 'clause':
                texts_to_refine.append({
                    'content': chunk.content,
                    'metadata': chunk.metadata
                })
        
        if texts_to_refine:
            semantic_chunks = self.semantic_chunker.chunk_multiple_texts(texts_to_refine)
            logger.info(f"Semantic refinement: {len(semantic_chunks)} chunks from {len(texts_to_refine)} large chunks")
            
            # Combine: keep small rule chunks, replace large ones with semantic chunks
            self.final_chunks = []
            
            for chunk in rule_chunks:
                if len(chunk.content) > 1000 and chunk.chunk_type == 'clause':
                    # Find corresponding semantic chunks
                    clause_id = chunk.clause_id
                    matching_semantic = [
                        sc for sc in semantic_chunks 
                        if sc.parent_chunk_id == clause_id
                    ]
                    self.final_chunks.extend(matching_semantic)
                else:
                    self.final_chunks.append(chunk)
        else:
            self.final_chunks = rule_chunks
        
        logger.info(f"✅ Hybrid chunking complete: {len(self.final_chunks)} final chunks")
        return self.final_chunks


if __name__ == "__main__":
    # Example usage
    sample_text = """
    회사는 이 계약에 따라 보험의 목적에 대하여 다음 각호의 손해를 보상합니다.
    1. 직접손해: 화재, 낙뢰, 파열 또는 폭발로 보험의 목적에 생긴 손해
    2. 소방손해: 화재를 소방하기 위하여 필요한 조치로 생긴 손해
    3. 피난손해: 화재가 발생한 때 피난으로 생긴 보험의 목적의 손해
    4. 잔존물 제거비용: 손해를 입은 보험의 목적의 잔존물을 제거하는데 드는 비용
    5. 손해방지비용: 손해의 방지 또는 경감을 위하여 지출한 필요 또는 유익한 비용
    """
    
    metadata = {
        'clause_id': '제11조',
        'title': '보상하는 손해',
        'clause_type': 'Coverage'
    }
    
    chunker = SemanticChunker()
    chunks = chunker.chunk_text(sample_text, metadata)
    
    print(f"\n✅ Created {len(chunks)} semantic chunks:")
    for chunk in chunks:
        print(f"\n{chunk.chunk_id} ({chunk.semantic_type}):")
        print(f"  {chunk.content[:100]}...")
