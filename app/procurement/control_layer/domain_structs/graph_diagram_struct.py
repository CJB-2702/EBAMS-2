"""Struct: pure string assembly of a GraphSummary's mermaid diagram source.

Relocated from the presentation-layer graph visualizer entrypoint (D88) into
the control layer so `GraphSummaryManager.recalculate()` can cache its output
onto `GraphSummary.swimlane_diagram` (D88 follow-up) instead of every read of
the graph visualizer page rebuilding it from scratch. No business logic here
(model_patterns.md/standards.md) — same "struct assembles, never decides"
discipline as every other struct in this app; it takes the member rows and
edges the caller already loaded and turns them into `flowchart LR` mermaid
source, nothing more.
"""

from __future__ import annotations


class MermaidSwimlaneBuilder:
    """Turns a graph's member rows and edges into mermaid `flowchart LR`
    source — three subgraphs (swimlanes), one per member type, edges drawn
    between them.
    """

    @staticmethod
    def build(
        *, demands, po_lines, shipment_lines, demand_po_edges, po_shipment_edges
    ) -> str:
        lines: list[str] = ["flowchart LR"]

        lines.append('  subgraph Demands["Demands"]')
        if demands:
            for demand in demands:
                label = MermaidSwimlaneBuilder._escape(
                    f"D{demand.pk}: {demand.part.part_number} x{demand.quantity_requested}"
                )
                lines.append(f'    D{demand.pk}["{label}"]')
        else:
            lines.append('    D_empty["(none)"]')
        lines.append("  end")

        lines.append('  subgraph POLines["PO Lines"]')
        if po_lines:
            for line in po_lines:
                label = MermaidSwimlaneBuilder._escape(
                    f"P{line.pk}: {line.purchase_order.po_number} L{line.line_number} "
                    f"{line.part.part_number} x{line.quantity_ordered}"
                )
                lines.append(f'    P{line.pk}["{label}"]')
        else:
            lines.append('    P_empty["(none)"]')
        lines.append("  end")

        lines.append('  subgraph ShipmentLines["Shipment Lines"]')
        if shipment_lines:
            for shipment_line in shipment_lines:
                label = MermaidSwimlaneBuilder._escape(
                    f"S{shipment_line.pk}: {shipment_line.shipment.shipment_number} "
                    f"{shipment_line.part.part_number} x{shipment_line.quantity}"
                )
                lines.append(f'    S{shipment_line.pk}["{label}"]')
        else:
            lines.append('    S_empty["(none)"]')
        lines.append("  end")

        for demand_id, po_line_id in demand_po_edges:
            lines.append(f"  D{demand_id} --> P{po_line_id}")
        for po_line_id, shipment_line_id in po_shipment_edges:
            lines.append(f"  P{po_line_id} --> S{shipment_line_id}")

        return "\n".join(lines)

    @staticmethod
    def _escape(text: str) -> str:
        # Mermaid node labels choke on double quotes and square brackets; a
        # plain part number / PO number never legitimately contains either, so
        # a straight substitution is enough — no need for a real escaper.
        return text.replace('"', "'").replace("[", "(").replace("]", ")")
