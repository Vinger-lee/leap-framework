-- ===========================================================================
-- LEAP Framework V2.0 - seed data
-- Idempotent: every statement uses INSERT ... ON CONFLICT DO NOTHING.
-- ===========================================================================

-- Pedagogical strategy library (LEAP-Framework-V2 section 9)
INSERT INTO pedagogical_strategies (strategy_id, name, description, applicable_scenarios, behavior_rules, version)
VALUES
    ('strategy_explanation', 'Explanation',
     '建立整体结构并讲解核心概念，适合背景知识不足或需要先建立框架的场景。',
     '["background_gap","concept_introduction","understanding_goal","missing_prerequisite"]',
     '["advance_organizer","framework","core_concepts","examples","understanding_check","summary"]',
     '1'),

    ('strategy_scaffolding', 'Scaffolding',
     '把复杂任务拆成学习者可逐步承担的子任务，并随能力提升逐步撤除支持。',
     '["task_too_complex","partial_capability","high_cognitive_load"]',
     '["decompose","prompt","partial_support","learner_attempt","reduce_support","independent_performance"]',
     '1'),

    ('strategy_socratic', 'Socratic Questioning',
     '通过追问暴露隐含假设、推理漏洞、概念矛盾与证据缺口。不得成为"永不解释"的约束。',
     '["shallow_reasoning","unstated_assumption","conceptual_conflict"]',
     '["probe_assumption","probe_evidence","probe_implication","switch_to_explanation_when_marginal_gain_low"]',
     '1'),

    ('strategy_correction', 'Correction',
     '针对错误概念、概念混淆与重复出现的同类错误进行定位与纠正。',
     '["misconception_active","concept_confusion","repeated_error","systematic_reasoning_bias"]',
     '["confirm_correct_parts","locate_error","counterexample","learner_reexplains","reassess","transfer_if_needed"]',
     '1'),

    ('strategy_worked_example', 'Worked Example',
     '在多次失败或提示依赖升高时提供完整示范；示范后必须安排自我解释与新问题。',
     '["repeated_failure","no_effective_strategy","rising_hint_dependency","demonstration_goal"]',
     '["full_demonstration","self_explanation","new_problem"]',
     '1'),

    ('strategy_retrieval_practice', 'Retrieval Practice',
     '要求学习者在缺少材料直接提示的条件下主动检索概念、定义、公式、流程或解题策略。',
     '["material_covered","needs_consolidation","retention_goal"]',
     '["prompt_active_recall","withhold_material","verify_retrieval"]',
     '1'),

    ('strategy_pbl', 'Problem-Based Learning',
     '以真实问题驱动学习，适合编程、工程、设计与数据分析类目标。',
     '["programming","engineering","design","data_analysis","integrated_project"]',
     '["real_problem","subtasks","implementation","feedback","iteration","integrated_application"]',
     '1'),

    ('strategy_cognitive_apprenticeship', 'Cognitive Apprenticeship',
     '通过示范、教练、支架与淡出培养真实任务能力。',
     '["authentic_task","procedural_skill","expert_practice"]',
     '["modeling","coaching","scaffolding","fading","independent_performance"]',
     '1'),

    ('strategy_transfer_probe', 'Transfer Probe',
     '通过改变表述、参数、数据、场景或任务结构，检验学习者掌握的是知识策略还是熟悉题型。',
     '["demonstrated_evidence","generalization_required"]',
     '["vary_representation","vary_parameters","vary_context","score_transfer"]',
     '1'),

    ('strategy_reflection', 'Reflection',
     '推动学习者执行计划-执行-监控-反思-调整循环；强度需与任务复杂度匹配。',
     '["task_completed","difficulty_encountered","strategy_selection"]',
     '["what_was_hardest","what_strategy_used","what_is_uncertain","why_it_works","would_it_generalize","next_time_plan"]',
     '1')
ON CONFLICT(strategy_id) DO NOTHING;
