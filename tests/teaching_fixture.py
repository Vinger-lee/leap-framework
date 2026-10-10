"""Explicit synthetic teaching pair for structural workflow tests only."""
from leap.runtime.delivery import html_teaching_text


def teaching_pair():
    point = {
        "point_id": "fixture.equation", "title": "Controlled equation fixture",
        "prerequisites": "An equality compares two real numbers; addition on both sides preserves their equality.",
        "principle": "Subtract the same constant from each side, then divide both sides by the same nonzero coefficient.",
        "steps": ["Subtract five from both sides of 3x+5=20 to obtain the equivalent equation 3x=15.",
                  "Divide both sides by the nonzero number three to obtain x=5, then check the original equation."],
        "worked_example": "Substitution gives 3*5+5=20, so x=5 satisfies the original equation under the real-number assumption.",
        "misconceptions": "Subtracting five on only one side changes the equation and fails to preserve its solution set.",
        "boundaries": "A zero coefficient cannot be divided out; 0x=0 has all real solutions while 0x=1 has none.",
        "comparison": "The expression 3x+5 has no equality to solve until a right-hand value and equality sign are supplied.",
        "practice": "Basic: solve 3x+5=20. Variation: solve 2x+4=10. Challenge: classify 0x=0 and 0x=1.",
        "transfer": "For ax+b=c, classify the zero coefficient first and use x=(c-b)/a only when a is nonzero.",
        "visualization": {"type": "labeled step trace", "selector": "#trace"},
    }
    resources = {"videos": [], "keywords": {"core": ["linear equation equality properties beginner"],
        "extension": ["linear equation zero coefficient cases"], "advanced": ["equivalent transformations solution set proof"]}}
    text = ["Learning resources"] + [v for tier in resources["keywords"].values() for v in tier]
    text += [v for k, v in point.items() if isinstance(v, str)] + point["steps"]
    html = '<!doctype html><html><body><div id="trace">' + "".join(f"<p>{v}</p>" for v in text) + '</div></body></html>'
    extension = "An independent inverse-operation check starts from x=5, multiplies both sides by three, adds five to both sides and recovers 3x+5=20. This explains why the solution sets coincide rather than merely testing one candidate."
    md = "---\ntitle: Controlled equation fixture\ntags: [test, equation]\naliases: [Synthetic pair]\n---\n\n# Learning resources\n\n[[Knowledge_Index]]\n\n" + "\n\n".join(text) + "\n\n> [!example]- Extended inverse check\n> " + extension + "\n"
    return md, html, {"resources": resources, "teaching_points": [point], "html_segments": text,
                      "markdown_extensions": [extension]}


def register_pair(service, session_id, node_id="fixture.equation"):
    service.save_knowledge_nodes(session_id, [{"node_id": node_id, "title": "Controlled fixture", "unit_tag": "fixture"}])
    md, html, manifest = teaching_pair()
    manifest["source_ids"] = [row["source_id"] for row in service.rows("SELECT source_id FROM evidence_sources WHERE session_id=?", (session_id,))]
    return service.save_teaching_package(session_id, node_id, "math", md, html, manifest)["package_id"]
