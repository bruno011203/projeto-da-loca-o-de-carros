"""Recalcula os números de página do sumário da Documentação Final.

Uso (na raiz do projeto):  python docs/fonte/atualizar_sumario.py
Precisa de Node.js (com o pacote docx), LibreOffice (soffice) e pdftotext (Poppler).

1. Gera o .docx com os números atuais de docs/fonte/sumario_paginas.json.
2. Converte para PDF e procura em que página cada título aparece.
3. Grava os números e gera de novo, até os números pararem de mudar.
A capa não é contada; a folha de rosto é a página 1 (NBR 14724).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

FONTE = Path(__file__).resolve().parent
DOCX = FONTE.parent / "Documentacao_Final.docx"
PAGINAS = FONTE / "sumario_paginas.json"
TITULOS = FONTE / "sumario_titulos.json"


def gerar():
    subprocess.run(["node", str(FONTE / "gerar_documentacao.js")], check=True)


def paginas_do_pdf(pasta):
    perfil = Path(pasta, "perfil").as_uri()
    env = dict(os.environ, SAL_USE_VCLPLUGIN="svp")
    subprocess.run(["soffice", f"-env:UserInstallation={perfil}", "--headless", "--convert-to", "pdf",
                    "--outdir", pasta, str(DOCX)], check=True, capture_output=True, env=env)
    pdf = Path(pasta, DOCX.with_suffix(".pdf").name)
    texto = subprocess.run(["pdftotext", str(pdf), "-"], check=True, capture_output=True, text=True).stdout
    return texto.split("\f")


def localizar(paginas_pdf, titulos):
    # O sumário termina na página que lista o último apêndice; o texto começa depois dela.
    ultimo = titulos[-1]["texto"]
    inicio = next(i for i, t in enumerate(paginas_pdf) if ultimo.split(" – ")[0] in t) + 1
    resultado, atual = {}, inicio
    for titulo in titulos:
        padrao = re.compile(r"(^|\n)\s*" + r"\s+".join(map(re.escape, titulo["texto"].split())) + r"\s*(\n|$)")
        for i in range(atual, len(paginas_pdf)):
            if padrao.search(paginas_pdf[i]):
                resultado[titulo["texto"]] = i   # índice 0 = capa; 1 = folha de rosto (página 1)
                atual = i
                break
        else:
            sys.exit(f"Título não encontrado no PDF: {titulo['texto']}")
    return resultado


def main():
    for rodada in range(1, 5):
        gerar()
        titulos = json.loads(TITULOS.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as pasta:
            novas = localizar(paginas_do_pdf(pasta), titulos)
        antigas = json.loads(PAGINAS.read_text(encoding="utf-8")) if PAGINAS.exists() else {}
        if novas == antigas:
            print(f"Sumário conferido na rodada {rodada}: {len(novas)} títulos com a página certa.")
            return
        PAGINAS.write_text(json.dumps(novas, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit("Os números do sumário não estabilizaram.")


if __name__ == "__main__":
    main()
