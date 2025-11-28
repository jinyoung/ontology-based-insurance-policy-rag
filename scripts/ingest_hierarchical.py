#!/usr/bin/env python3
"""
계층적 조-항-호 구조로 PDF 보험약관 Ingestion

- Article (조)
- Paragraph (항)
- Item (호)
- 각 레벨별 임베딩
- 조항 간 상호 참조 관계
"""
import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

import argparse
from loguru import logger
from openai import OpenAI
from neo4j import GraphDatabase

from src.config.settings import settings
from src.parsers.pdf_parser import PolicyPDFParser
from src.parsers.clause_extractor import ClauseExtractor


def update_progress(progress_file: str, stage: str, percent: int, detail: str = ""):
    """Update progress file for frontend"""
    if progress_file:
        try:
            with open(progress_file, 'w') as f:
                json.dump({
                    "stage": stage,
                    "percent": percent,
                    "detail": detail
                }, f)
        except:
            pass


def main():
    parser = argparse.ArgumentParser(description="Ingest PDF with hierarchical structure (조-항-호)")
    parser.add_argument("--pdf", type=str, required=True, help="Path to PDF file")
    parser.add_argument("--product-code", type=str, required=True, help="Product code")
    parser.add_argument("--product-name", type=str, required=True, help="Product name")
    parser.add_argument("--version-id", type=str, required=True, help="Version ID")
    parser.add_argument("--max-clauses", type=int, default=None, help="Max clauses to process")
    parser.add_argument("--progress-file", type=str, default=None, help="Progress file path for status updates")
    
    args = parser.parse_args()
    progress_file = args.progress_file
    
    pdf_file = Path(args.pdf)
    product_code = args.product_code
    product_name = args.product_name
    version_id = args.version_id
    max_clauses = args.max_clauses
    
    if not pdf_file.exists():
        logger.error(f"PDF 파일을 찾을 수 없습니다: {pdf_file}")
        return
    
    logger.info("="*80)
    logger.info("📦 계층적 PDF Ingestion 시작 (조-항-호)")
    logger.info("="*80)
    logger.info(f"PDF: {pdf_file.name}")
    logger.info(f"Product: {product_name} ({product_code})")
    logger.info(f"Version: {version_id}")
    if max_clauses:
        logger.info(f"Max Clauses: {max_clauses}")
    logger.info("="*80)
    
    # Initialize clients
    openai_client = OpenAI(api_key=settings.openai_api_key)
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password)
    )
    
    stats = {
        'pdf_file': pdf_file.name,
        'pages': 0,
        'total_clauses': 0,
        'processed_clauses': 0,
        'paragraphs': 0,
        'items': 0,
        'cross_references': 0,
        'embeddings': 0,
        'nodes_created': 0
    }
    
    try:
        # Step 1: Parse PDF
        logger.info("\n[Step 1] PDF 파싱 중...")
        update_progress(progress_file, "PDF 파싱 중...", 5, f"파일: {pdf_file.name}")
        
        pdf_parser = PolicyPDFParser(str(pdf_file))
        pages = pdf_parser.extract_text_by_page()
        text = pdf_parser.extract_full_text()
        stats['pages'] = len(pages)
        logger.info(f"  ✅ {stats['pages']}페이지 추출")
        update_progress(progress_file, "PDF 파싱 완료", 10, f"{stats['pages']}페이지 추출됨")
        
        # Step 2: Extract clauses
        logger.info("\n[Step 2] 조항 추출 중...")
        update_progress(progress_file, "조항 추출 중...", 12, "약관에서 조항 구조 분석 중")
        
        extractor = ClauseExtractor()
        all_clauses = extractor.extract_clauses(text)
        stats['total_clauses'] = len(all_clauses)
        
        # Limit clauses if needed
        clauses = all_clauses[:max_clauses] if max_clauses else all_clauses
        stats['processed_clauses'] = len(clauses)
        logger.info(f"  ✅ 처리할 조항: {stats['processed_clauses']}개")
        update_progress(progress_file, "조항 추출 완료", 15, f"총 {stats['processed_clauses']}개 조항 추출")
        
        # Step 3: Extract paragraphs and items
        logger.info("\n[Step 3] 항(項)과 호(號) 추출 중...")
        
        all_paragraphs = []
        all_items = []
        
        for idx, clause in enumerate(clauses, 1):
            update_progress(progress_file, "항/호 추출 중...", 15 + int((idx / len(clauses)) * 7), 
                           f"조항 {idx}/{len(clauses)} - {clause.clause_id}")
            paragraphs, items = extractor.extract_paragraphs_and_items(clause)
            all_paragraphs.extend(paragraphs)
            all_items.extend(items)
        
        stats['paragraphs'] = len(all_paragraphs)
        stats['items'] = len(all_items)
        logger.info(f"  ✅ 항: {stats['paragraphs']}개, 호: {stats['items']}개")
        update_progress(progress_file, "항/호 추출 완료", 22, f"항 {stats['paragraphs']}개, 호 {stats['items']}개 추출")
        
        # Step 4: Find cross-references (from Paragraphs and Items)
        logger.info("\n[Step 4] 항/호 간 상호 참조 탐색 중...")
        update_progress(progress_file, "상호 참조 분석 중...", 25, "조항 간 참조 관계 탐색")
        all_references = []
        
        # Find references from Paragraphs
        for paragraph in all_paragraphs:
            refs = extractor.find_cross_references(paragraph.text)
            for ref in refs:
                all_references.append({
                    'from_id': paragraph.paragraph_id,
                    'from_type': 'paragraph',
                    'to_id': ref['to'],
                    'to_type': ref['type']
                })
        
        # Find references from Items
        for item in all_items:
            refs = extractor.find_cross_references(item.text)
            for ref in refs:
                all_references.append({
                    'from_id': item.item_id,
                    'from_type': 'item',
                    'to_id': ref['to'],
                    'to_type': ref['type']
                })
        
        stats['cross_references'] = len(all_references)
        logger.info(f"  ✅ {stats['cross_references']}개 상호 참조 발견")
        update_progress(progress_file, "상호 참조 분석 완료", 30, f"{stats['cross_references']}개 상호 참조 발견")
        
        # Step 5: Generate embeddings
        logger.info("\n[Step 5] 임베딩 생성 중...")
        total_items_to_embed = len(clauses) + len(all_paragraphs) + len(all_items)
        embedded_count = 0
        
        # Clause embeddings
        logger.info(f"  [5.1] 조(條) 임베딩 생성 중... ({len(clauses)}개)")
        for i, clause in enumerate(clauses, 1):
            update_progress(progress_file, "조(條) 임베딩 생성 중...", 30 + int((embedded_count / total_items_to_embed) * 30), 
                           f"조항 {i}/{len(clauses)} - {clause.clause_id}")
            try:
                response = openai_client.embeddings.create(
                    model=settings.embedding_model,
                    input=clause.full_text
                )
                clause.embedding = response.data[0].embedding
                stats['embeddings'] += 1
                embedded_count += 1
            except Exception as e:
                logger.warning(f"  ✗ 조항 {clause.clause_id} 임베딩 실패: {e}")
                embedded_count += 1
        
        logger.info(f"  ✅ {len(clauses)}개 조항 임베딩 완료")
        
        # Paragraph embeddings
        logger.info(f"  [5.2] 항(項) 임베딩 생성 중... ({len(all_paragraphs)}개)")
        for i, paragraph in enumerate(all_paragraphs, 1):
            update_progress(progress_file, "항(項) 임베딩 생성 중...", 30 + int((embedded_count / total_items_to_embed) * 30), 
                           f"항 {i}/{len(all_paragraphs)} - {paragraph.paragraph_id}")
            try:
                response = openai_client.embeddings.create(
                    model=settings.embedding_model,
                    input=paragraph.text
                )
                paragraph.embedding = response.data[0].embedding
                stats['embeddings'] += 1
                embedded_count += 1
            except Exception as e:
                logger.warning(f"  ✗ 항 {paragraph.paragraph_id} 임베딩 실패: {e}")
                embedded_count += 1
        
        logger.info(f"  ✅ {len(all_paragraphs)}개 항 임베딩 완료")
        
        # Item embeddings
        logger.info(f"  [5.3] 호(號) 임베딩 생성 중... ({len(all_items)}개)")
        for i, item in enumerate(all_items, 1):
            update_progress(progress_file, "호(號) 임베딩 생성 중...", 30 + int((embedded_count / total_items_to_embed) * 30), 
                           f"호 {i}/{len(all_items)} - {item.item_id}")
            try:
                response = openai_client.embeddings.create(
                    model=settings.embedding_model,
                    input=item.text
                )
                item.embedding = response.data[0].embedding
                stats['embeddings'] += 1
                embedded_count += 1
            except Exception as e:
                logger.warning(f"  ✗ 호 {item.item_id} 임베딩 실패: {e}")
                embedded_count += 1
        
        logger.info(f"  ✅ {len(all_items)}개 호 임베딩 완료")
        logger.info(f"  ✅ 총 {stats['embeddings']}개 임베딩 생성 완료")
        update_progress(progress_file, "임베딩 생성 완료", 60, f"총 {stats['embeddings']}개 임베딩 생성")
        
        # Step 6: Load to Neo4j
        logger.info("\n[Step 6] Neo4j에 로딩 중...")
        update_progress(progress_file, "Neo4j 로딩 시작...", 62, "상품 및 버전 생성 중")
        
        with driver.session() as session:
            # Create product
            logger.info(f"  상품 생성: {product_name}")
            session.run("""
                MERGE (prod:InsuranceProduct {code: $code})
                SET prod.name = $name,
                    prod.kind = 'personal_injury',
                    prod.lineOfBusiness = 'personal'
                """,
                code=product_code,
                name=product_name
            )
            
            # Create version
            logger.info(f"  버전 생성: {version_id}")
            session.run("""
                MATCH (prod:InsuranceProduct {code: $product_code})
                MERGE (ver:PolicyVersion {versionId: $version_id})
                SET ver.effectiveFrom = date(),
                    ver.documentUrl = $pdf_path
                MERGE (prod)-[:HAS_POLICY_VERSION]->(ver)
                """,
                product_code=product_code,
                version_id=version_id,
                pdf_path=str(pdf_file)
            )
            
            # Create articles (조)
            logger.info(f"  조(條) 로딩: {len(clauses)}개")
            update_progress(progress_file, "조(條) 노드 생성 중...", 65, f"0/{len(clauses)} 조 저장됨")
            for idx, clause in enumerate(clauses, 1):
                update_progress(progress_file, "조(條) 노드 생성 중...", 65 + int((idx / len(clauses)) * 5), 
                               f"{idx}/{len(clauses)} - {clause.clause_id}")
                session.run("""
                    MATCH (ver:PolicyVersion {versionId: $version_id})
                    MERGE (a:Article {articleId: $article_id})
                    SET a.number = $number,
                        a.title = $title,
                        a.text = $text,
                        a.clauseType = $clause_type,
                        a.embedding = $embedding
                    MERGE (ver)-[:HAS_ARTICLE]->(a)
                    """,
                    version_id=version_id,
                    article_id=clause.clause_id,
                    number=clause.article_number,
                    title=clause.title,
                    text=clause.full_text,
                    clause_type=clause.clause_type or 'General',
                    embedding=clause.embedding if hasattr(clause, 'embedding') else None
                )
                stats['nodes_created'] += 1
            
            logger.info(f"  ✅ {len(clauses)}개 조 로딩 완료")
            update_progress(progress_file, "조(條) 노드 생성 완료", 70, f"{len(clauses)}개 조 저장됨")
            
            # Create paragraphs (항)
            logger.info(f"  항(項) 로딩: {len(all_paragraphs)}개")
            for idx, paragraph in enumerate(all_paragraphs, 1):
                update_progress(progress_file, "항(項) 노드 생성 중...", 70 + int((idx / max(len(all_paragraphs), 1)) * 5), 
                               f"{idx}/{len(all_paragraphs)} - {paragraph.paragraph_id}")
                session.run("""
                    MATCH (a:Article {articleId: $parent_article})
                    MERGE (p:Paragraph {paragraphId: $paragraph_id})
                    SET p.number = $number,
                        p.text = $text,
                        p.embedding = $embedding
                    MERGE (a)-[:HAS_PARAGRAPH]->(p)
                    """,
                    parent_article=paragraph.parent_clause,
                    paragraph_id=paragraph.paragraph_id,
                    number=paragraph.number,
                    text=paragraph.text,
                    embedding=paragraph.embedding if hasattr(paragraph, 'embedding') else None
                )
                stats['nodes_created'] += 1
            
            logger.info(f"  ✅ {len(all_paragraphs)}개 항 로딩 완료")
            update_progress(progress_file, "항(項) 노드 생성 완료", 75, f"{len(all_paragraphs)}개 항 저장됨")
            
            # Create items (호)
            logger.info(f"  호(號) 로딩: {len(all_items)}개")
            for i, item in enumerate(all_items, 1):
                update_progress(progress_file, "호(號) 노드 생성 중...", 75 + int((i / max(len(all_items), 1)) * 5), 
                               f"{i}/{len(all_items)} - {item.item_id}")
                try:
                    logger.debug(f"    [{i}/{len(all_items)}] {item.item_id} -> {item.parent_paragraph}")
                    session.run("""
                        MATCH (p:Paragraph {paragraphId: $parent_paragraph})
                        MERGE (i:Item {itemId: $item_id})
                        SET i.number = $number,
                            i.text = $text,
                            i.embedding = $embedding
                        MERGE (p)-[:HAS_ITEM]->(i)
                        """,
                        parent_paragraph=item.parent_paragraph,
                        item_id=item.item_id,
                        number=item.number,
                        text=item.text,
                        embedding=item.embedding if hasattr(item, 'embedding') else None
                    )
                    stats['nodes_created'] += 1
                except Exception as e:
                    logger.error(f"  ✗ 호 {item.item_id} 저장 실패: {e}")
            
            logger.info(f"  ✅ {len(all_items)}개 호 로딩 완료")
            update_progress(progress_file, "호(號) 노드 생성 완료", 80, f"{len(all_items)}개 호 저장됨")
            
            # Create cross-references (Paragraph/Item → Paragraph/Item/Article)
            # - 구체적 항/호 명시: Paragraph/Item로 연결
            # - 조만 언급: Article로 연결
            logger.info(f"  상호 참조 관계 생성: {len(all_references)}개")
            update_progress(progress_file, "상호 참조 관계 생성 중...", 82, f"0/{len(all_references)} REFERS_TO 관계 생성")
            refs_created = 0
            
            for ref_idx, ref in enumerate(all_references, 1):
                update_progress(progress_file, "상호 참조 관계 생성 중...", 
                               82 + int((ref_idx / max(len(all_references), 1)) * 8), 
                               f"{ref_idx}/{len(all_references)} - {ref['from_id']} → {ref['to_id']}")
                try:
                    # Determine from_node label and property
                    if ref['from_type'] == 'paragraph':
                        from_label = 'Paragraph'
                        from_prop = 'paragraphId'
                    elif ref['from_type'] == 'item':
                        from_label = 'Item'
                        from_prop = 'itemId'
                    else:
                        continue
                    
                    # Determine to_node label and property
                    if ref['to_type'] == 'clause':
                        # 조만 언급된 경우: Article로 연결
                        to_label = 'Article'
                        to_prop = 'articleId'
                        to_id = ref['to_id']
                    elif ref['to_type'] == 'paragraph':
                        # 구체적 항 명시: Paragraph로 연결
                        to_label = 'Paragraph'
                        to_prop = 'paragraphId'
                        to_id = ref['to_id']
                    elif ref['to_type'] == 'item':
                        # 구체적 호 명시: Item로 연결
                        to_label = 'Item'
                        to_prop = 'itemId'
                        to_id = ref['to_id']
                    else:
                        continue
                    
                    # Create REFERS_TO relationship
                    query = f"""
                        MATCH (from_node:{from_label} {{{from_prop}: $from_id}})
                        MATCH (to_node:{to_label} {{{to_prop}: $to_id}})
                        MERGE (from_node)-[:REFERS_TO]->(to_node)
                    """
                    
                    session.run(query, from_id=ref['from_id'], to_id=to_id)
                    refs_created += 1
                    logger.debug(f"    참조: {ref['from_id']} → {to_id} ({to_label})")
                    
                except Exception as e:
                    logger.warning(f"  ✗ 참조 관계 생성 실패 ({ref['from_id']} -> {ref['to_id']}): {e}")
            
            logger.info(f"  ✅ {refs_created}개 상호 참조 관계 생성 완료")
            update_progress(progress_file, "상호 참조 관계 생성 완료", 90, f"{refs_created}개 REFERS_TO 관계 생성됨")
        
        # Step 7: Generate recommended queries (optional)
        update_progress(progress_file, "추천 질의 생성 중...", 92, "LLM으로 추천 질의 생성 중")
        
        # Summary
        update_progress(progress_file, "완료!", 100, f"조: {stats['processed_clauses']}개, 항: {stats['paragraphs']}개, 호: {stats['items']}개 저장")
        logger.info("\n" + "="*80)
        logger.info("✅ 계층적 Ingestion 완료!")
        logger.info("="*80)
        logger.info(f"PDF 파일: {stats['pdf_file']}")
        logger.info(f"페이지: {stats['pages']}개")
        logger.info(f"총 조항: {stats['total_clauses']}개")
        logger.info(f"처리된 조항: {stats['processed_clauses']}개")
        logger.info(f"항(項): {stats['paragraphs']}개")
        logger.info(f"호(號): {stats['items']}개")
        logger.info(f"상호 참조: {stats['cross_references']}개")
        logger.info(f"임베딩: {stats['embeddings']}개")
        logger.info(f"노드 생성: {stats['nodes_created']}개")
        logger.info("="*80)
        
        # Step 8: Clean up uploaded file
        if 'uploads' in str(pdf_file):
            try:
                import os
                if pdf_file.exists():
                    os.remove(pdf_file)
                    logger.info(f"🗑️ 업로드된 파일 삭제됨: {pdf_file.name}")
            except Exception as cleanup_error:
                logger.warning(f"파일 삭제 실패: {cleanup_error}")
        
    except Exception as e:
        logger.error(f"❌ Ingestion 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.close()


if __name__ == "__main__":
    main()

