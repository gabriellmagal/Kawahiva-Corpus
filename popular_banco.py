import os
import sqlite3
import pandas as pd
import unicodedata
import re
from praatio import textgrid

BASE = os.path.dirname(os.path.abspath(__file__))
PASTA_TG = os.path.join(BASE, "TextGrid")
PLANILHA = os.path.join(BASE, "Portal Japiim ProDoclin.xlsx")
BANCO_DADOS = os.path.join(BASE, "corpus.db")

def limpar_para_busca(txt):
    if not isinstance(txt, str): return ""
    txt = re.sub(r'<[^>]+>', '', txt)
    txt = re.sub(r"[’‘´ʼ`]", "'", txt)
    txt = txt.replace('\xa0', ' ')
    txt = unicodedata.normalize('NFC', txt)
    txt = txt.lower()
    txt = "".join(char for char in txt if char.isalpha() or char == "'" or char.isspace())
    return " ".join(txt.split()).strip()

def extrair_texto_tg(caminho_tg):
    tg = textgrid.openTextgrid(caminho_tg, True)
    vernacula = ""
    fonetica = ""
    if 'words' in tg.tierNames:
        labels = [entry.label for entry in tg.getTier('words').entries if entry.label.strip()]
        vernacula = " ".join(labels)
    if 'phones' in tg.tierNames:
        labels_f = [entry.label for entry in tg.getTier('phones').entries if entry.label.strip()]
        fonetica = " ".join(labels_f)
    return vernacula, fonetica

def processar():
    if not os.path.exists(PLANILHA):
        print("❌ Erro: Planilha não encontrada.")
        return

    print("📊 Lendo e limpando planilha Excel...")
    df_glosas = pd.read_excel(PLANILHA)
    df_glosas.columns = df_glosas.columns.str.strip() 

    col_vernacula = 'Vernácula'
    col_glosa = 'Glosa'

    df_glosas['match_key'] = df_glosas[col_vernacula].astype(str).apply(limpar_para_busca)
    df_glosas = df_glosas.drop_duplicates(subset=['match_key'])

    conn = sqlite3.connect(BANCO_DADOS)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS corpus")
    cursor.execute("""
        CREATE TABLE corpus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arquivo TEXT,
            vernacula TEXT,
            fonetica TEXT,
            glosa TEXT
        )
    """)

    print("📁 Processando TextGrids (Busca Inteligente)...")
    arquivos = [f.replace(".TextGrid", "") for f in os.listdir(PASTA_TG) if f.endswith(".TextGrid")]
    
    count = 0
    for nome in arquivos:
        caminho_tg = os.path.join(PASTA_TG, f"{nome}.TextGrid")
        try:
            vern_original, fon_original = extrair_texto_tg(caminho_tg)
            chave_busca = limpar_para_busca(vern_original)
            
            # 1. TENTA CORRESPONDÊNCIA EXATA
            match = df_glosas[df_glosas['match_key'] == chave_busca]
            
            # 2. SE FALHAR, TENTA BUSCA PARCIAL (Caso do tavijara tavijarahẽa)
            if match.empty and len(chave_busca) > 3:
                # Vê se a palavra do TG está dentro de alguma entrada da planilha
                match = df_glosas[df_glosas['match_key'].str.contains(chave_busca, regex=False)]
            
            # 3. SE AINDA FALHAR, TENTA O CONTRÁRIO (Início da palavra)
            if match.empty and len(chave_busca) > 4:
                prefixo = chave_busca[:4]
                match = df_glosas[df_glosas['match_key'].str.startswith(prefixo)]

            if not match.empty:
                # Pega a primeira glosa encontrada
                glosa = str(match[col_glosa].values[0])
            else:
                glosa = "—"
                print(f"⚠️ Sem glosa: [{chave_busca}] no arquivo {nome}")

            cursor.execute(
                "INSERT INTO corpus (arquivo, vernacula, fonetica, glosa) VALUES (?, ?, ?, ?)",
                (nome, vern_original, fon_original, glosa)
            )
            count += 1
        except Exception as e:
            print(f"⚠️ Erro em {nome}: {e}")
    
    conn.commit()
    conn.close()
    print(f"\n✅ CONCLUÍDO! {count}/100 arquivos processados com sucesso.")

if __name__ == "__main__":
    processar()