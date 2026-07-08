#!/usr/bin/env python3
"""
Generates sample_docs/fnol_08_pdf_sample.pdf — a plain, original-layout FNOL
form (not a reproduction of any insurer's copyrighted form) used purely to
prove the agent can extract fields from PDF as well as TXT input.

Run: python scripts/generate_sample_pdf.py
"""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT_PATH = Path(__file__).resolve().parent.parent / "sample_docs" / "fnol_08_pdf_sample.pdf"

LINES = [
    ("title", "FIRST NOTICE OF LOSS - AUTO CLAIM"),
    ("gap", ""),
    ("field", "Policy Number: PA-7724-2026"),
    ("field", "Policyholder Name: Rachel Kim"),
    ("field", "Effective Dates: 10/01/2025 - 10/01/2026"),
    ("gap", ""),
    ("field", "Date of Loss: 07/03/2026"),
    ("field", "Time of Loss: 12:15 PM"),
    ("field", "Location of Loss: 500 Market St Parking Garage, Level 2, Seattle, WA"),
    ("field", "Description of Accident: Policyholder scraped the driver-side door against a"),
    ("wrap", "concrete pillar while parking. Minor paint transfer and a small dent."),
    ("wrap", "No other vehicles or people involved."),
    ("gap", ""),
    ("field", "Claimant: Rachel Kim"),
    ("field", "Third Parties: None"),
    ("field", "Contact Details: rachel.kim@email.com, (555) 512-9087"),
    ("gap", ""),
    ("field", "Asset Type: Hatchback"),
    ("field", "Asset ID: JTDBT4K30G1234567"),
    ("field", "Estimated Damage: $980.00"),
    ("gap", ""),
    ("field", "Claim Type: Collision"),
    ("field", "Attachments: door_dent_photo.jpg"),
    ("field", "Initial Estimate: $980.00"),
]


def build_pdf():
    OUT_PATH.parent.mkdir(exist_ok=True)
    c = canvas.Canvas(str(OUT_PATH), pagesize=letter)
    width, height = letter
    y = height - 72
    left_margin = 72

    for kind, text in LINES:
        if kind == "title":
            c.setFont("Helvetica-Bold", 14)
            c.drawString(left_margin, y, text)
            y -= 26
        elif kind == "gap":
            y -= 10
        else:  # field / wrap continuation line
            c.setFont("Helvetica", 10)
            c.drawString(left_margin, y, text)
            y -= 16

    c.save()
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    build_pdf()
