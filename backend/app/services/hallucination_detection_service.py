# -*- coding: utf-8 -*-
"""
幻觉检测和引用溯源服务（LLM 语义级版本）
使用 LLM 做语义级幻觉检测，而非简单的字符串匹配
"""
import logging
from typing import List, Dict, Any
from dashscope import Generation
from app.core.config import settings

logger = logging.getLogger(__name__)


class HallucinationDetectionService:
    """
    幻觉检测和引用溯源服务（LLM 版本）
    """

    def __init__(self):
        self.min_similarity = 0.3
        self.high_confidence_threshold = 0.7
        logger.info("幻觉检测和引用溯源服务(LLM版)初始化完成")

    def _build_hallucination_prompt(self, answer: str, chunks: List[Dict[str, Any]]) -> str:
        """构建 LLM 幻觉检测 prompt"""
        context_parts = []
        for i, chunk in enumerate(chunks[:10], 1):
            content = chunk.get('content', '') if isinstance(chunk, dict) else getattr(chunk, 'content', '') or ''
            file_name = chunk.get('file_name', '') if isinstance(chunk, dict) else getattr(chunk, 'file_name', '') or ''
            title = chunk.get('title', '') if isinstance(chunk, dict) else getattr(chunk, 'title', '') or file_name or '未知来源'
            if len(content) > 500:
                content = content[:500] + '...'
            context_parts.append(f'[{i}] {title}: {content}')

        context_text = '\n'.join(context_parts)

        return (
            f'你是一个专业的幻觉检测助手。请根据提供的参考文档，判断以下回答是否包含幻觉内容。\n\n'
            f'<reference_documents>\n{context_text}\n</reference_documents>\n\n'
            f'<answer_to_check>\n{answer}\n</answer_to_check>\n\n'
            f'请逐句分析回答中的每个声明，判断其是否能被参考文档支持。\n'
            f'请以 JSON 格式输出，格式如下：\n'
            f'```json\n'
            f'{{\n'
            f'  "claims": [\n'
            f'    {{"text": "声明内容", "supported": true/false, "confidence": 0.0-1.0, "source_ids": [1,2]}}\n'
            f'  ]\n'
            f'}}\n'
            f'```\n'
            f'其中 supported 表示是否被文档支持，confidence 表示支持程度(0-1)，source_ids 表示支持的文档编号列表。'
        )

    def _parse_llm_json(self, text: str) -> Dict[str, Any]:
        """从 LLM 输出中提取 JSON"""
        import json
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json ... ``` 块
        import re
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试提取第一个 { ... } 块
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        return {}

    def detect_hallucinations(self, answer: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        使用 LLM 检测回答中的幻觉内容

        Args:
            answer: 生成的回答
            chunks: 检索到的文档片段

        Returns:
            包含幻觉检测结果的字典
        """
        if not answer or not chunks:
            return {
                'has_hallucinations': False,
                'claims': [],
                'hallucination_rate': 0.0,
                'overall_confidence': 1.0
            }

        try:
            prompt = self._build_hallucination_prompt(answer, chunks)
            
            messages = [
                {"role": "system", "content": "你是一个专业的幻觉检测助手，擅长分析文本是否基于提供的参考资料。"},
                {"role": "user", "content": prompt},
            ]

            response = Generation.call(
                api_key=settings.dashscope_api_key,
                model="qwen-turbo",
                messages=messages,
                result_format="message",
                temperature=0.1,
            )

            if response.status_code != 200:
                logger.warning(f"[HallucinationDetection] LLM 调用失败 {response.status_code}，降级为简单匹配")
                return self._fallback_detect(answer, chunks)

            content = response.output.choices[0].message.get("content", "")
            result_json = self._parse_llm_json(content)
            
            claims_data = result_json.get("claims", [])
            if not claims_data:
                return self._fallback_detect(answer, chunks)

            # 处理结果
            results = []
            hallucination_count = 0
            total_confidence = 0.0

            for i, claim_data in enumerate(claims_data):
                is_supported = claim_data.get("supported", False)
                confidence = claim_data.get("confidence", 0.0)
                source_ids = claim_data.get("source_ids", [])
                
                if not is_supported:
                    hallucination_count += 1
                
                total_confidence += confidence

                # 找到对应的 chunks
                supporting_chunks = []
                for sid in source_ids:
                    if 1 <= sid <= len(chunks):
                        supporting_chunks.append({
                            'chunk': chunks[sid - 1],
                            'similarity': confidence,
                            'matching_text': '',
                        })

                results.append({
                    'claim': claim_data.get("text", ""),
                    'claim_index': i,
                    'start_pos': answer.find(claim_data.get("text", "")),
                    'end_pos': answer.find(claim_data.get("text", "")) + len(claim_data.get("text", "")),
                    'is_hallucination': not is_supported,
                    'confidence': confidence,
                    'supporting_chunks': supporting_chunks[:3],
                })

            hallucination_rate = hallucination_count / len(results) if results else 0.0
            overall_confidence = total_confidence / len(results) if results else 0.0

            return {
                'has_hallucinations': hallucination_count > 0,
                'claims': results,
                'hallucination_rate': hallucination_rate,
                'overall_confidence': overall_confidence,
                'total_claims': len(results),
                'hallucination_count': hallucination_count,
            }

        except Exception as e:
            logger.error(f"[HallucinationDetection] LLM 检测失败: {e}，降级为简单匹配")
            return self._fallback_detect(answer, chunks)

    def _fallback_detect(self, answer: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """降级方案：使用关键词重叠的简单匹配"""
        if not answer or not chunks:
            return {
                'has_hallucinations': False,
                'claims': [],
                'hallucination_rate': 0.0,
                'overall_confidence': 1.0
            }

        # 按句子分割
        import re
        sentences = [s.strip() for s in re.split(r'[。！？；\n]', answer) if s.strip()]
        
        results = []
        hallucination_count = 0
        total_confidence = 0.0

        for i, sentence in enumerate(sentences):
            if len(sentence) < 5:
                continue
            
            # 提取关键词
            sent_words = set(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{2,}', sentence.lower()))
            
            best_similarity = 0.0
            for chunk in chunks:
                content = chunk.get('content', '') if isinstance(chunk, dict) else getattr(chunk, 'content', '') or ''
                chunk_words = set(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{2,}', content.lower()))
                
                if not sent_words or not chunk_words:
                    continue
                
                # Jaccard 相似度
                intersection = sent_words & chunk_words
                union = sent_words | chunk_words
                similarity = len(intersection) / len(union) if union else 0
                best_similarity = max(best_similarity, similarity)
            
            is_hallucination = best_similarity < 0.15
            if is_hallucination:
                hallucination_count += 1
            
            total_confidence += best_similarity
            
            results.append({
                'claim': sentence,
                'claim_index': i,
                'start_pos': answer.find(sentence),
                'end_pos': answer.find(sentence) + len(sentence),
                'is_hallucination': is_hallucination,
                'confidence': best_similarity,
                'supporting_chunks': [],
            })

        hallucination_rate = hallucination_count / len(results) if results else 0.0
        overall_confidence = total_confidence / len(results) if results else 0.0

        return {
            'has_hallucinations': hallucination_count > 0,
            'claims': results,
            'hallucination_rate': hallucination_rate,
            'overall_confidence': overall_confidence,
            'total_claims': len(results),
            'hallucination_count': hallucination_count,
        }

    def generate_citations(self, answer: str, chunks: List[Dict[str, Any]]) -> tuple:
        """
        为回答生成引用溯源
        """
        detection_result = self.detect_hallucinations(answer, chunks)
        
        if not detection_result['claims']:
            return answer, []

        citations = []
        citation_map = {}
        citation_counter = 1

        for claim_result in detection_result['claims']:
            if not claim_result['is_hallucination'] and claim_result['supporting_chunks']:
                best_chunk = claim_result['supporting_chunks'][0]['chunk']
                chunk_id = best_chunk.get('chunk_id', '') if isinstance(best_chunk, dict) else getattr(best_chunk, 'chunk_id', '')
                
                if chunk_id and chunk_id not in citation_map:
                    citation_map[chunk_id] = citation_counter
                    citations.append({
                        'citation_id': citation_counter,
                        'chunk_id': chunk_id,
                        'file_name': best_chunk.get('file_name', '') if isinstance(best_chunk, dict) else getattr(best_chunk, 'file_name', '') or '',
                        'content': (best_chunk.get('content', '') if isinstance(best_chunk, dict) else getattr(best_chunk, 'content', '') or '')[:200],
                        'confidence': claim_result['confidence'],
                    })
                    citation_counter += 1

        cited_answer = answer
        offset = 0

        for claim_result in sorted(detection_result['claims'], key=lambda x: x.get('start_pos', 0), reverse=True):
            if not claim_result['is_hallucination'] and claim_result['supporting_chunks']:
                best_chunk = claim_result['supporting_chunks'][0]['chunk']
                chunk_id = best_chunk.get('chunk_id', '') if isinstance(best_chunk, dict) else getattr(best_chunk, 'chunk_id', '')
                
                if chunk_id in citation_map:
                    citation_id = citation_map[chunk_id]
                    insert_pos = claim_result.get('end_pos', 0) + offset
                    cited_answer = cited_answer[:insert_pos] + f" [{citation_id}]" + cited_answer[insert_pos:]
                    offset += len(f" [{citation_id}]")

        return cited_answer, citations

    def add_citations_to_answer(self, answer: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        为回答添加引用和幻觉检测信息
        """
        cited_answer, citations = self.generate_citations(answer, chunks)
        detection_result = self.detect_hallucinations(answer, chunks)

        return {
            'original_answer': answer,
            'cited_answer': cited_answer,
            'citations': citations,
            'hallucination_detection': detection_result,
        }


# 单例模式
_hallucination_service = None


def get_hallucination_detection_service() -> HallucinationDetectionService:
    """
    获取幻觉检测服务实例
    """
    global _hallucination_service
    if _hallucination_service is None:
        _hallucination_service = HallucinationDetectionService()
    return _hallucination_service
