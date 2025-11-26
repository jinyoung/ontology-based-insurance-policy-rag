"""
PDF Parser for Insurance Policy Documents
Extracts text while preserving structure
"""
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger
import re


class PolicyPDFParser:
    """
    Parse insurance policy PDF documents
    Preserves document structure and metadata
    """
    
    def __init__(self, pdf_path: str):
        """
        Initialize PDF parser
        
        Args:
            pdf_path: Path to the PDF file
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.doc = fitz.open(str(self.pdf_path))
        self.total_pages = len(self.doc)
        logger.info(f"Loaded PDF: {self.pdf_path.name} ({self.total_pages} pages)")
    
    def extract_text_by_page(self) -> List[Dict[str, Any]]:
        """
        Extract text from all pages with metadata
        
        Returns:
            List of dicts with page number, text, and metadata
        """
        pages = []
        
        for page_num in range(self.total_pages):
            page = self.doc[page_num]
            text = page.get_text("text")
            
            # Get page dimensions
            rect = page.rect
            
            page_data = {
                'page_number': page_num + 1,
                'text': text,
                'width': rect.width,
                'height': rect.height,
                'char_count': len(text),
                'word_count': len(text.split())
            }
            
            pages.append(page_data)
            logger.debug(f"Extracted page {page_num + 1}: {page_data['word_count']} words")
        
        return pages
    
    def extract_full_text(self) -> str:
        """
        Extract all text from the PDF as a single string
        
        Returns:
            Complete document text
        """
        full_text = []
        
        for page_num in range(self.total_pages):
            page = self.doc[page_num]
            text = page.get_text("text")
            full_text.append(text)
        
        combined_text = "\n\n".join(full_text)
        logger.info(f"Extracted full text: {len(combined_text)} characters")
        
        return combined_text
    
    def extract_tables(self, page_num: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Extract tables from PDF (basic implementation)
        
        Args:
            page_num: Specific page number (1-indexed), or None for all pages
            
        Returns:
            List of table data
        """
        tables = []
        
        pages_to_process = [page_num - 1] if page_num else range(self.total_pages)
        
        for pnum in pages_to_process:
            page = self.doc[pnum]
            
            # Try to detect table-like structures using text blocks
            blocks = page.get_text("blocks")
            
            # Simple heuristic: consecutive blocks with similar x-coordinates
            potential_tables = []
            current_table = []
            
            for block in blocks:
                x0, y0, x1, y1, text, block_no, block_type = block
                
                # Check if this looks like a table cell (aligned blocks)
                if len(current_table) > 0:
                    last_block = current_table[-1]
                    # If y-coordinates are close and x-coordinates vary (columns)
                    if abs(y0 - last_block[1]) < 20:
                        current_table.append(block)
                    else:
                        if len(current_table) > 2:
                            potential_tables.append(current_table)
                        current_table = [block]
                else:
                    current_table = [block]
            
            if len(current_table) > 2:
                potential_tables.append(current_table)
            
            for table_blocks in potential_tables:
                table_text = "\n".join([b[4] for b in table_blocks])
                tables.append({
                    'page_number': pnum + 1,
                    'text': table_text,
                    'block_count': len(table_blocks)
                })
        
        logger.info(f"Extracted {len(tables)} potential tables")
        return tables
    
    def detect_sections(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect major sections in the document
        
        Args:
            text: Document text
            
        Returns:
            List of detected sections
        """
        sections = []
        
        # Patterns for section headers
        patterns = [
            r'^제\s*\d+\s*장',  # Chapter: 제1장
            r'^제\s*\d+\s*절',  # Section: 제1절
            r'^\d+\.\s+[가-힣]{2,}',  # Numbered sections: 1. 제목
            r'^[A-Z][a-z]+\s+\d+',  # Article 1, Section 2 etc.
        ]
        
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            for pattern in patterns:
                if re.match(pattern, line):
                    sections.append({
                        'line_number': i + 1,
                        'text': line,
                        'type': 'section_header'
                    })
                    break
        
        logger.info(f"Detected {len(sections)} section headers")
        return sections
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Extract PDF metadata
        
        Returns:
            Dictionary of metadata
        """
        metadata = {
            'filename': self.pdf_path.name,
            'total_pages': self.total_pages,
            'file_size_mb': self.pdf_path.stat().st_size / (1024 * 1024),
        }
        
        # Get PDF info
        pdf_metadata = self.doc.metadata
        if pdf_metadata:
            metadata.update({
                'title': pdf_metadata.get('title', ''),
                'author': pdf_metadata.get('author', ''),
                'subject': pdf_metadata.get('subject', ''),
                'creator': pdf_metadata.get('creator', ''),
                'producer': pdf_metadata.get('producer', ''),
                'creation_date': pdf_metadata.get('creationDate', ''),
                'modification_date': pdf_metadata.get('modDate', ''),
            })
        
        return metadata
    
    def close(self):
        """Close the PDF document"""
        self.doc.close()
        logger.info("PDF document closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def parse_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Convenience function to parse a PDF and return all extracted data
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Dictionary with all parsed data
    """
    with PolicyPDFParser(pdf_path) as parser:
        result = {
            'metadata': parser.get_metadata(),
            'full_text': parser.extract_full_text(),
            'pages': parser.extract_text_by_page(),
            'tables': parser.extract_tables(),
        }
    
    return result


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pdf_parser.py <path_to_pdf>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    with PolicyPDFParser(pdf_path) as parser:
        metadata = parser.get_metadata()
        print(f"\nMetadata: {metadata}")
        
        full_text = parser.extract_full_text()
        print(f"\nTotal characters: {len(full_text)}")
        print(f"\nFirst 500 characters:\n{full_text[:500]}")
