"""
packaging/generate_docs_pdf.py - Generates comprehensive production PDF guides
for Miss Minutes & Jarvis AI Desktop Assistant.
"""

import sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)


def generate_setup_guide_pdf(output_path: Path):
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#FF5722'),
        alignment=1, # Center
        spaceAfter=10,
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#555555'),
        alignment=1,
        spaceAfter=20,
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#1E88E5'),
        spaceBefore=14,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#222222'),
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#333333'),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3,
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#222222'),
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white,
    )

    story = []

    # Title & Header
    story.append(Paragraph("MISS MINUTES & JARVIS AI ASSISTANT", title_style))
    story.append(Paragraph("Production Setup, Multilingual Architecture & Multi-LLM User Manual", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#FF5722'), spaceAfter=15))

    # Section 1: Executive Overview
    story.append(Paragraph("1. Executive Overview & Architecture", h1_style))
    story.append(Paragraph(
        "Miss Minutes & Jarvis is a state-of-the-art dual-agent desktop assistant designed for Windows 10/11. "
        "The system coordinates two synchronized personas: Miss Minutes (warm, lively, user-facing TVA clock companion) "
        "and Jarvis (authoritative, technically precise capability architect). They feature sequential turn-taking dialogue, "
        "fluent bilingual comprehension in Telugu and English, hands-free voice activity detection, and deep desktop capability execution.",
        body_style
    ))

    # Section 2: Turn-Taking & Voice Layer
    story.append(Paragraph("2. Turn-Taking Dialogue & Voice Intelligence", h1_style))
    story.append(Paragraph(
        "Miss Minutes and Jarvis communicate collaboratively without overlapping speech. Miss Minutes acknowledges the user's "
        "intent and provides warm conversational rapport, while Jarvis executes the underlying technical actions and provides verification.",
        body_style
    ))
    story.append(Paragraph("• <b>Hands-Free Continuous Listening</b>: Continuous RMS-energy Voice Activity Detection (VAD) with 0.85s silence termination. No manual mic clicks required.", bullet_style))
    story.append(Paragraph("• <b>Quiet / Standby Mode</b>: Voice triggers like 'remain quiet', 'silent ga undu', or 'aagu' place the assistants in standby until asked to resume.", bullet_style))
    story.append(Paragraph("• <b>Neural Edge-TTS Voices</b>: Miss Minutes uses <i>te-IN-ShrutiNeural</i> (expressive Telugu voice) and Jarvis uses <i>te-IN-MohanNeural</i> (commanding male voice).", bullet_style))
    story.append(Paragraph("• <b>Zero-Lag Audio Caching</b>: Frequently spoken acknowledgments and greetings are cached in memory for 0ms playback latency.", bullet_style))

    # Section 3: Real LLM Engine Backbone
    story.append(Paragraph("3. Multi-Provider LLM Intelligence Backbone", h1_style))
    story.append(Paragraph(
        "The intelligence layer operates a resilient, self-healing chain across leading proprietary and open-source models:",
        body_style
    ))

    llm_table_data = [
        [Paragraph("Provider", table_header_style), Paragraph("Models", table_header_style), Paragraph("Key Features", table_header_style)],
        [
            Paragraph("<b>Google Gemini</b>", table_cell_style),
            Paragraph("gemini-2.5-flash, gemini-2.0-flash", table_cell_style),
            Paragraph("Sub-second multimodal reasoning, native Telugu comprehension, structured JSON output.", table_cell_style),
        ],
        [
            Paragraph("<b>OpenAI & Compatible</b>", table_cell_style),
            Paragraph("gpt-4o, gpt-4o-mini, Ollama (localhost)", table_cell_style),
            Paragraph("Industry standard structured tool calling; seamless local inference via Ollama or LM Studio.", table_cell_style),
        ],
        [
            Paragraph("<b>Groq Cloud</b>", table_cell_style),
            Paragraph("llama-3.3-70b-versatile, llama-3.1-8b", table_cell_style),
            Paragraph("Ultra-high inference throughput (800+ tokens/sec) for zero conversational lag.", table_cell_style),
        ],
        [
            Paragraph("<b>Hugging Face Hub</b>", table_cell_style),
            Paragraph("Llama-3.3-70B, Qwen-2.5-72B", table_cell_style),
            Paragraph("Access to open-source foundation models via Serverless Inference API router.", table_cell_style),
        ],
        [
            Paragraph("<b>Free Public AI</b>", table_cell_style),
            Paragraph("openai-fast, mistral", table_cell_style),
            Paragraph("Key-free instant online LLM provider ensuring full functionality with zero setup.", table_cell_style),
        ],
    ]

    t_llm = Table(llm_table_data, colWidths=[110, 160, 260])
    t_llm.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E88E5')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#DDDDDD')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#FAFAFA'), colors.white]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_llm)
    story.append(Spacer(1, 10))

    # Section 4: Adaptive Learning
    story.append(Paragraph("4. Contextual Adaptive Language & NLP Learning", h1_style))
    story.append(Paragraph(
        "The ContextLearner engine analyzes every interaction in real-time, adapting Miss Minutes and Jarvis to the user:",
        body_style
    ))
    story.append(Paragraph("• <b>Vocabulary Extraction</b>: Tracks frequent Tenglish words ('workload', 'seconds lo', 'cheyyi', 'choodu') and mirrors them in conversation.", bullet_style))
    story.append(Paragraph("• <b>Personal Fact Memory</b>: Automatically records user details (name, tasks, preferences) and incorporates them across sessions.", bullet_style))
    story.append(Paragraph("• <b>Custom Shortcuts & Aliases</b>: Learns expressions such as 'wa ante whatsapp' or 'yt ante youtube' dynamically.", bullet_style))
    story.append(Paragraph("• <b>Persistent Profile</b>: Persists all learned context to ~/.miss_minutes/learned_context.json across reboots.", bullet_style))

    # Section 5: Capabilities & Desktop Tools
    story.append(Paragraph("5. Desktop Capabilities & System Automation", h1_style))
    story.append(Paragraph("• <b>Google Chrome</b>: Launch browser, open URLs, manage search queries and tabs.", bullet_style))
    story.append(Paragraph("• <b>WhatsApp</b>: Native desktop client protocol (whatsapp://) with instant fallback to web.whatsapp.com.", bullet_style))
    story.append(Paragraph("• <b>Screen Reader</b>: PySide6 primary display capture + Windows Media OCR to read questions or text off your screen.", bullet_style))
    story.append(Paragraph("• <b>Rapid Multi-Source Research</b>: Parallel queries to Wikipedia and DuckDuckGo with LLM synthesis in Telugu+English.", bullet_style))
    story.append(Paragraph("• <b>Security Boundary</b>: Default-DENY security model; destructive commands, shell scripts, and unauthorized paths are blocked.", bullet_style))

    # Section 6: Quick Start Guide
    story.append(Paragraph("6. Quick Start & Execution Commands", h1_style))
    story.append(Paragraph("<b>1. Launch Desktop Assistant:</b><br/><code>python main.py</code> or double-click <code>launch_miss_minutes.bat</code>", body_style))
    story.append(Paragraph("<b>2. Run Full System Diagnostics:</b><br/><code>python main.py --diagnostics</code>", body_style))
    story.append(Paragraph("<b>3. Run Complete Test Suite (185 Tests):</b><br/><code>python -m pytest tests/</code>", body_style))

    doc.build(story)
    print(f"[OK] Generated PDF guide: {output_path}")


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent
    pdf_target = out_dir / "Jarvis_Setup_Guide.pdf"
    generate_setup_guide_pdf(pdf_target)
