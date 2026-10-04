"""Explicit, repeatable import of public reference documents. Never sends case data."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vte_review.knowledge import KnowledgeStore

REFERENCES = [
    ("[UK guideline] NICE NG158 — VTE diagnosis, treatment, cancer and follow-up", "ABC", "pdf",
     "https://www.nice.org.uk/guidance/ng158/resources/venous-thromboembolic-diseases-diagnosis-management-and-thrombophilia-testing-pdf-66141847001797", "anticoagulation"),
    ("[US label] XARELTO rivaroxaban — dosage, organ function, bleeding and interactions", "ABC", "html",
     "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=7e9ab975-db2f-423c-a089-bc5a73313609", "Treatment of DVT"),
    ("[US label] Methotrexate — marrow, hepatic, renal toxicity and interactions", "BC", "html",
     "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=22e10810-16fb-4c84-bccf-972405b77ef8", "methotrexate"),
    ("[US label] Sulfamethoxazole / trimethoprim — methotrexate and warfarin interactions", "BC", "html",
     "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=7f25bff3-0e86-4bec-b293-54b68347867f", "Methotrexate"),
]


class ReadableHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip=0; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in {"script","style","noscript"}:self.skip+=1
        if not self.skip and tag in {"p","div","br","tr","li","h1","h2","h3","h4"}:self.parts.append("\n")
        if not self.skip and tag in {"td","th"}:self.parts.append(" | ")
    def handle_endtag(self,tag):
        if tag in {"script","style","noscript"}:self.skip=max(0,self.skip-1)
        if not self.skip and tag in {"p","tr","li","h1","h2","h3","h4"}:self.parts.append("\n")
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)
    def text(self):return "\n".join(" ".join(line.split()) for line in "".join(self.parts).splitlines() if line.strip())


def main():
    import httpx
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs",default="runs")
    args=parser.parse_args()
    root=Path(args.runs).resolve(); folder=root/"reference_sources";folder.mkdir(parents=True,exist_ok=True)
    date=datetime.now(timezone.utc).date().isoformat(); documents=[]; manifest=[]
    with httpx.Client(timeout=45,follow_redirects=True) as client:
        for n,(title,roles,kind,url,marker) in enumerate(REFERENCES,1):
            response=client.get(url,headers={"User-Agent":"VTE-Research-Reference-Import/0.4"})
            response.raise_for_status(); raw=response.content
            if len(raw)>20*1024*1024:raise ValueError("Reference exceeds import limit")
            if kind=="pdf":
                from pypdf import PdfReader
                reader=PdfReader(io.BytesIO(raw))
                text="\n\n".join(f"[Page {i+1}]\n"+(p.extract_text() or "") for i,p in enumerate(reader.pages))
            else:
                html=ReadableHTML();html.feed(response.text);text=html.text()
                if "dailymed.nlm.nih.gov" in url and "Label:" in text:
                    text=text[text.index("Label:"):]
            if marker.lower() not in text.lower() or len(text)<2000:
                raise ValueError("Reference verification failed: "+title)
            digest=hashlib.sha256(raw).hexdigest(); stem=f"{n:02d}-{digest[:12]}"
            (folder/(stem+"."+kind)).write_bytes(raw)
            (folder/(stem+".txt")).write_text(text,encoding="utf-8")
            version=f"retrieved {date}; original sha256 {digest[:12]}"
            documents.append({"title":title,"source":url,"version":version,"roles":list(roles),"synthetic":False,"text":text})
            manifest.append({"title":title,"url":url,"retrieved_at":date,"sha256":digest,"file":stem+"."+kind,"characters":len(text)})
            print(title+f": {len(text):,} characters",flush=True)
    result=KnowledgeStore(root/"knowledge.sqlite3").add_many(documents)
    (folder/"manifest.json").write_text(json.dumps({"sources":manifest,"import":result},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":main()
