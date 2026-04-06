import pandas as pd

# 1. Configurações
arquivo_excel = 'Portal Japiim ProDoclin.xlsx'
mapeamento = {
    'ngw': 'ᵑɡ ʋ', 'mb': 'ᵐb', 'nd': 'ⁿd', 'ng': 'ᵑɡ',
    'tx': 'dʒ', 'y': 'ɯ', 'ỹ': 'ɯ ̃', "'": 'ʔ',
    'p': 'p', 't': 't', 'k': 'k', 'r': 'ɾ', 'v': 'ʋ', 'h': 'x', 'j': 'dʒ',
    'a': 'a', 'e': 'e', 'i': 'i', 'o': 'o', 'u': 'u',
    'ã': 'ã', 'ẽ': 'ẽ', 'ĩ': 'ĩ', 'õ': 'õ', 'ũ': 'ũ'
}

def g2p_kawahiva(texto):
    texto = str(texto).lower().strip()
    res = []
    i = 0
    while i < len(texto):
        match = False
        for size in [3, 2, 1]:
            chunk = texto[i:i+size]
            if chunk in mapeamento:
                res.append(mapeamento[chunk])
                i += size
                match = True
                break
        if not match: i += 1
    return " ".join(res)

# 2. Ler a planilha
df = pd.read_excel(arquivo_excel, header=1)

# 3. Extrair TODAS as palavras individuais
set_palavras_unicas = set()
for p_composta in df.iloc[:, 1].dropna():
    # Quebra "oji yinung" em ["oji", "yinung"]
    palavras = str(p_composta).strip().split()
    for pal in palavras:
        set_palavras_unicas.add(pal)

# 4. Gerar o Dicionário Limpo
with open('kawahiva_lexicon.txt', 'w', encoding='utf-8') as f:
    # Ordena alfabeticamente para facilitar a conferência
    for p in sorted(list(set_palavras_unicas)):
        fones = g2p_kawahiva(p)
        if fones:
            f.write(f"{p} {fones}\n")

print(f"Dicionário corrigido gerado com {len(set_palavras_unicas)} palavras individuais.")