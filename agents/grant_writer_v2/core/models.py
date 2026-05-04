"""
MODEL_REGISTRY — maps use-case keys to OpenRouter model IDs.
Each entry is overridable via the matching V2_MODEL_* env var (set in config.py).
Import v2_settings to resolve at runtime.
"""
from agents.grant_writer_v2.config import v2_settings

MODEL_REGISTRY: dict[str, str] = {
    "layer1_reranker":           v2_settings.V2_MODEL_LAYER1_RERANKER,
    "layer2_agent":              v2_settings.V2_MODEL_LAYER2_AGENT,
    "layer2_program_identifier": v2_settings.V2_MODEL_LAYER2_PROGRAM_IDENTIFIER,
    "layer2_rule_evaluator":     v2_settings.V2_MODEL_LAYER2_RULE_EVALUATOR,
    "layer3_extractor":          v2_settings.V2_MODEL_LAYER3_EXTRACTOR,
    "layer4_per_program":        v2_settings.V2_MODEL_LAYER4_PER_PROGRAM,
    "layer4_consolidator":       v2_settings.V2_MODEL_LAYER4_CONSOLIDATOR,
    "layer5_seo":                v2_settings.V2_MODEL_LAYER5_SEO,
}
