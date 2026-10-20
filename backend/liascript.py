def build_liascript(doc) -> str:
    out = [f"# {doc.title}\n"]

    if doc.summary:
        out += ["## Shrnutí\n", doc.summary, ""]

    if doc.questions:
        out.append("## Kvíz\n")
        for i, q in enumerate(doc.questions, 1):
            out.append(f"**{i}. {q.question}**\n")
            for idx, opt in enumerate(q.options):
                mark = "X" if idx == q.correct else " "
                out.append(f"- [({mark})] {opt}")
            if q.explanation:
                out += ["", "    ************", f"    {q.explanation}", "    ************"]
            out.append("")

    if doc.cards:
        out.append("## Kartičky\n")
        for c in doc.cards:
            out += [f"### {c.front}\n", c.back, ""]

    return "\n".join(out)