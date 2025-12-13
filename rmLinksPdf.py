#!/usr/bin/env python3

import os
import sys
from PyPDF2 import PdfReader, PdfWriter

def remove_links(input_pdf, output_pdf):
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for page in reader.pages:
        # Remove link annotations
        if "/Annots" in page:
            new_annots = []
            for annot in page["/Annots"]:
                obj = annot.get_object()
                # If annotation contains a URI (a hyperlink), skip it
                if "/A" in obj and "/URI" in obj["/A"]:
                    continue
                new_annots.append(annot)

            if new_annots:
                page["/Annots"] = new_annots
            else:
                del page["/Annots"]

        writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)

    print(f"✔ Cleaned: {output_pdf}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python remove_links.py input1.pdf [input2.pdf ...]")
        sys.exit(1)

    for pdf in sys.argv[1:]:
        if not os.path.isfile(pdf):
            print(f"File not found: {pdf}")
            continue

        output = pdf.replace(".pdf", "_nolinks.pdf")
        remove_links(pdf, output)

