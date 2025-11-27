"""
Clause Extractor for Insurance Policy Documents
Extracts clauses based on Korean legal document structure (조/항/호)
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class Clause:
    """Represents a policy clause (조)"""
    clause_id: str  # e.g., "제11조"
    article_number: int  # e.g., 11
    title: str  # e.g., "보상하는 손해"
    full_text: str
    clause_type: Optional[str] = None  # Coverage, Exclusion, Condition, Definition
    section_path: str = ""  # e.g., "제11조" or "도난위험특약>제2조"
    parent_section: Optional[str] = None  # For special clauses (특약)
    page_number: Optional[int] = None
    items: List[str] = None  # 항/호 items
    
    def __post_init__(self):
        if self.items is None:
            self.items = []


@dataclass
class Paragraph:
    """Represents a paragraph within a clause (항)"""
    paragraph_id: str  # e.g., "제1조제1항"
    number: int
    text: str
    parent_clause: str
    embedding: Optional[List[float]] = None


@dataclass
class Item:
    """Represents an item within a paragraph (호)"""
    item_id: str  # e.g., "제1조제1항제1호"
    number: int
    text: str
    parent_paragraph: str
    embedding: Optional[List[float]] = None


class ClauseExtractor:
    """
    Extract structured clauses from insurance policy documents
    Based on Korean legal document patterns (조/항/호)
    """
    
    # Regex patterns for Korean legal structures
    CLAUSE_PATTERN = r'제\s*(\d+)\s*조\s*[(（]([^)）]+)[)）]?'  # 제11조(보상하는 손해)
    CLAUSE_PATTERN_NO_TITLE = r'제\s*(\d+)\s*조(?![가-힣])'  # 제11조
    ARTICLE_PATTERN = r'①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩|⑪|⑫|⑬|⑭|⑮'  # Circled numbers
    ARTICLE_PATTERN_ALT = r'제?\s*(\d+)\s*항'  # 제1항 or 1항
    ITEM_PATTERN = r'^\s*(\d+)\s*\.'  # 1. 2. 3. ...
    SPECIAL_CLAUSE_PATTERN = r'【([^】]+특별약관)】|<([^>]+특별약관)>'  # Special clause markers
    
    # Note: Clause type detection is handled by LLM during semantic chunking
    # These are just hints for initial categorization
    
    def __init__(self):
        """Initialize the clause extractor"""
        self.clauses: List[Clause] = []
        self.special_sections: List[str] = []
    
    def extract_clauses(self, text: str) -> List[Clause]:
        """
        Extract all clauses from document text
        
        Args:
            text: Full document text
            
        Returns:
            List of extracted Clause objects
        """
        self.clauses = []
        lines = text.split('\n')
        
        current_clause = None
        current_text = []
        current_special_section = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Check for special clause markers (특별약관)
            special_match = re.search(self.SPECIAL_CLAUSE_PATTERN, line)
            if special_match:
                current_special_section = special_match.group(1) or special_match.group(2)
                logger.debug(f"Found special section: {current_special_section}")
                continue
            
            # Check for clause pattern
            clause_match = re.match(self.CLAUSE_PATTERN, line)
            if clause_match:
                # Save previous clause
                if current_clause:
                    current_clause.full_text = '\n'.join(current_text).strip()
                    # Note: clause_type will be determined by LLM during semantic chunking
                    current_clause.clause_type = self._get_hint_from_title(current_clause.title)
                    self.clauses.append(current_clause)
                
                # Start new clause
                article_num = int(clause_match.group(1))
                title = clause_match.group(2).strip()
                clause_id = f"제{article_num}조"
                
                section_path = clause_id
                if current_special_section:
                    section_path = f"{current_special_section}>{clause_id}"
                
                current_clause = Clause(
                    clause_id=clause_id,
                    article_number=article_num,
                    title=title,
                    full_text="",
                    section_path=section_path,
                    parent_section=current_special_section,
                    clause_type=None  # Will be determined by LLM during chunking
                )
                current_text = [line]
                
                logger.debug(f"Found clause: {clause_id} - {title}")
            
            elif current_clause:
                current_text.append(line)
        
        # Save last clause
        if current_clause:
            current_clause.full_text = '\n'.join(current_text).strip()
            # Note: clause_type will be determined by LLM during semantic chunking
            current_clause.clause_type = self._get_hint_from_title(current_clause.title)
            self.clauses.append(current_clause)
        
        logger.info(f"✅ Extracted {len(self.clauses)} clauses")
        return self.clauses
    
    def _get_hint_from_title(self, title: str) -> Optional[str]:
        """
        Get a basic hint about clause type from title only.
        This is just a preliminary categorization - the actual type
        will be determined accurately by LLM during semantic chunking.
        
        Args:
            title: Clause title
            
        Returns:
            Basic hint or None (will be refined by LLM)
        """
        title_lower = title.lower()
            
        # Very basic hints from common title patterns
        if "보상하지" in title_lower or "면책" in title_lower:
            return "Exclusion"
        elif "보상하는" in title_lower or "담보" in title_lower:
            return "Coverage"
        elif "정의" in title_lower or "용어" in title_lower:
            return "Definition"
        elif "조건" in title_lower or "청구" in title_lower or "의무" in title_lower:
            return "Condition"
        
        # Return None - will be determined by LLM
        return None
    
    def extract_items_from_clause(self, clause: Clause) -> List[str]:
        """
        Extract enumerated items (호) from a clause
        
        Args:
            clause: Clause object
            
        Returns:
            List of item texts
        """
        items = []
        lines = clause.full_text.split('\n')
        
        current_item = []
        
        for line in lines:
            line = line.strip()
            
            # Check for item pattern (1. 2. 3. ...)
            item_match = re.match(self.ITEM_PATTERN, line)
            
            if item_match:
                # Save previous item
                if current_item:
                    items.append(' '.join(current_item))
                
                # Start new item
                current_item = [line]
            elif current_item:
                # Continue current item
                current_item.append(line)
        
        # Save last item
        if current_item:
            items.append(' '.join(current_item))
        
        clause.items = items
        logger.debug(f"Extracted {len(items)} items from {clause.clause_id}")
        
        return items
    
    def extract_special_clauses(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract special clauses (특별약관) sections
        
        Args:
            text: Full document text
            
        Returns:
            List of special clause metadata
        """
        special_clauses = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            match = re.search(self.SPECIAL_CLAUSE_PATTERN, line)
            if match:
                name = match.group(1) or match.group(2)
                special_clauses.append({
                    'name': name,
                    'line_number': i + 1,
                    'marker': line.strip()
                })
                logger.debug(f"Found special clause: {name}")
        
        logger.info(f"Extracted {len(special_clauses)} special clauses")
        return special_clauses
    
    def get_clause_by_id(self, clause_id: str) -> Optional[Clause]:
        """
        Get a specific clause by ID
        
        Args:
            clause_id: Clause identifier (e.g., "제11조")
            
        Returns:
            Clause object or None
        """
        for clause in self.clauses:
            if clause.clause_id == clause_id:
                return clause
        return None
    
    def get_clauses_by_type(self, clause_type: str) -> List[Clause]:
        """
        Get all clauses of a specific type
        
        Args:
            clause_type: Coverage, Exclusion, Condition, or Definition
            
        Returns:
            List of matching clauses
        """
        return [c for c in self.clauses if c.clause_type == clause_type]
    
    def get_clauses_by_special_section(self, section_name: str) -> List[Clause]:
        """
        Get all clauses under a special section (특약)
        
        Args:
            section_name: Special section name
            
        Returns:
            List of clauses in that section
        """
        return [c for c in self.clauses if c.parent_section == section_name]
    
    def extract_paragraphs_and_items(self, clause: Clause) -> Tuple[List[Paragraph], List[Item]]:
        """
        Extract paragraphs (항) and items (호) from a clause with hierarchical structure
        
        Args:
            clause: Clause object
            
        Returns:
            Tuple of (paragraphs, items)
        """
        paragraphs = []
        items = []
        
        lines = clause.full_text.split('\n')
        
        # Circled number mapping (①, ②, ③...)
        circled_map = {
            '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
            '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10,
            '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15
        }
        
        current_paragraph = None
        current_paragraph_text = []
        current_item = None
        current_item_text = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # Check for paragraph marker (①, ②, etc.)
            circled_found = None
            for symbol, num in circled_map.items():
                if symbol in stripped:
                    circled_found = (symbol, num)
                    break
            
            if circled_found:
                # Save previous item (if any) before starting new paragraph
                if current_item:
                    current_item.text = '\n'.join(current_item_text).strip()
                    items.append(current_item)
                    logger.debug(f"Saved item before new paragraph: {current_item.item_id}")
                
                # Save previous paragraph
                if current_paragraph:
                    current_paragraph.text = '\n'.join(current_paragraph_text).strip()
                    paragraphs.append(current_paragraph)
                
                # Start new paragraph
                para_num = circled_found[1]
                para_id = f"{clause.clause_id}제{para_num}항"
                current_paragraph = Paragraph(
                    paragraph_id=para_id,
                    number=para_num,
                    text="",
                    parent_clause=clause.clause_id
                )
                current_paragraph_text = [stripped]
                current_item = None
                current_item_text = []
                
                logger.debug(f"Found paragraph: {para_id}")
                continue
            
            # Check for item pattern (1. 2. 3. ...)
            item_match = re.match(r'^\s*(\d+)\s*\.', stripped)
            if item_match and current_paragraph:
                # Save previous item
                if current_item:
                    current_item.text = '\n'.join(current_item_text).strip()
                    items.append(current_item)
                
                # Start new item
                item_num = int(item_match.group(1))
                item_id = f"{current_paragraph.paragraph_id}제{item_num}호"
                current_item = Item(
                    item_id=item_id,
                    number=item_num,
                    text="",
                    parent_paragraph=current_paragraph.paragraph_id
                )
                current_item_text = [stripped]
                
                logger.debug(f"Found item: {item_id}")
                continue
            
            # Accumulate text
            if current_item:
                current_item_text.append(stripped)
            elif current_paragraph:
                current_paragraph_text.append(stripped)
        
        # Save last paragraph/item
        if current_item:
            current_item.text = '\n'.join(current_item_text).strip()
            items.append(current_item)
        if current_paragraph:
            current_paragraph.text = '\n'.join(current_paragraph_text).strip()
            paragraphs.append(current_paragraph)
        
        # If no paragraphs found, create a single paragraph with clause text
        if not paragraphs:
            para_id = f"{clause.clause_id}제1항"
            paragraphs.append(Paragraph(
                paragraph_id=para_id,
                number=1,
                text=clause.full_text,
                parent_clause=clause.clause_id
            ))
        
        logger.info(f"Extracted {len(paragraphs)} paragraphs and {len(items)} items from {clause.clause_id}")
        return paragraphs, items
    
    def find_cross_references(self, text: str) -> List[Dict[str, str]]:
        """
        Find cross-references to other clauses in text
        
        Patterns:
        - 제11조
        - 제3조 제2항
        - 제1조제1항제1호
        
        Args:
            text: Text to search for references
            
        Returns:
            List of reference dictionaries with 'from', 'to', 'type'
        """
        references = []
        
        # Pattern 1: 제X조
        clause_refs = re.findall(r'제\s*(\d+)\s*조(?![가-힣])', text)
        for ref in clause_refs:
            references.append({
                'to': f'제{ref}조',
                'type': 'clause'
            })
        
        # Pattern 2: 제X조 제Y항
        para_refs = re.findall(r'제\s*(\d+)\s*조\s*제\s*(\d+)\s*항', text)
        for clause_num, para_num in para_refs:
            references.append({
                'to': f'제{clause_num}조제{para_num}항',
                'type': 'paragraph'
            })
        
        # Pattern 3: 제X조제Y항제Z호
        item_refs = re.findall(r'제\s*(\d+)\s*조제\s*(\d+)\s*항제\s*(\d+)\s*호', text)
        for clause_num, para_num, item_num in item_refs:
            references.append({
                'to': f'제{clause_num}조제{para_num}항제{item_num}호',
                'type': 'item'
            })
        
        # Remove duplicates
        seen = set()
        unique_refs = []
        for ref in references:
            key = (ref['to'], ref['type'])
            if key not in seen:
                seen.add(key)
                unique_refs.append(ref)
        
        return unique_refs
    
    def to_dict(self) -> List[Dict[str, Any]]:
        """
        Convert extracted clauses to dictionary format
        
        Returns:
            List of clause dictionaries
        """
        return [
            {
                'clause_id': c.clause_id,
                'article_number': c.article_number,
                'title': c.title,
                'full_text': c.full_text,
                'clause_type': c.clause_type,
                'section_path': c.section_path,
                'parent_section': c.parent_section,
                'item_count': len(c.items) if c.items else 0,
                'items': c.items
            }
            for c in self.clauses
        ]


def extract_clauses_from_text(text: str) -> List[Clause]:
    """
    Convenience function to extract clauses from text
    
    Args:
        text: Document text
        
    Returns:
        List of Clause objects
    """
    extractor = ClauseExtractor()
    clauses = extractor.extract_clauses(text)
    
    # Extract items for each clause
    for clause in clauses:
        extractor.extract_items_from_clause(clause)
    
    return clauses


if __name__ == "__main__":
    # Example usage
    sample_text = """
    【도난위험 특별약관】
    
    제1조(보상하는 손해) 회사는 보험증권에 기재된 보험의 목적에 대하여 도난으로 인한 손해를 보상합니다.
    ① 도난으로 인한 직접적인 손해
    ② 도난물품의 회수비용
    
    제2조(보상하지 아니하는 손해) 회사는 다음의 손해는 보상하지 아니합니다.
    1. 계약자, 피보험자의 고의 또는 중대한 과실로 생긴 손해
    2. 전쟁, 혁명 등으로 생긴 손해
    3. 지진, 분화 등 천재지변으로 생긴 손해
    
    제3조(자기부담금) 회사가 보상할 손해액에서 자기부담금을 공제하고 지급합니다.
    """
    
    extractor = ClauseExtractor()
    clauses = extractor.extract_clauses(sample_text)
    
    print(f"\n✅ Extracted {len(clauses)} clauses:")
    for clause in clauses:
        print(f"\n{clause.clause_id} ({clause.clause_type}): {clause.title}")
        print(f"  Section path: {clause.section_path}")
        extractor.extract_items_from_clause(clause)
        if clause.items:
            print(f"  Items: {len(clause.items)}")
