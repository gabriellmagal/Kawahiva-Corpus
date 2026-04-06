# =============================================================
#  atualizar_corpus.R — Pipeline automático Kawahiva
#
#  Execute este script sempre que adicionar novos arquivos
#  ao corpus. Ele detecta automaticamente o que é novo
#  e processa apenas esses arquivos.
#
#  Como usar:
#    Rscript atualizar_corpus.R
#  Ou no RStudio: source("atualizar_corpus.R")
# =============================================================

library(emuR)
library(wrassp)

# ── Configuração ────────────────────────────────────────────
WAV_DIR  <- "C:/Users/Omnitel/Desktop/Kawahiva/Audio"
TG_DIR   <- "C:/Users/Omnitel/Desktop/Kawahiva/TextGrid"
DB_DIR   <- "C:/Users/Omnitel/Desktop/Kawahiva/emuDB"
DB_NAME  <- "kawahiva"
COLECAO  <- file.path(DB_DIR, "colecao_temp")
db_path  <- file.path(DB_DIR, paste0(DB_NAME, "_emuDB"))

cat("════════════════════════════════════════\n")
cat(" Pipeline Kawahiva — Atualização\n")
cat("════════════════════════════════════════\n\n")

# ── 1. Detectar arquivos novos ───────────────────────────────
wavs_audio <- tools::file_path_sans_ext(
  list.files(WAV_DIR, pattern = "\\.wav$", ignore.case = TRUE))
tgs_tg     <- tools::file_path_sans_ext(
  list.files(TG_DIR,  pattern = "\\.TextGrid$"))

# Apenas arquivos que têm os dois (wav + TextGrid)
novos_candidatos <- intersect(wavs_audio, tgs_tg)

# Verificar quais já existem no emuDB
if (dir.exists(db_path)) {
  kawahiva    <- load_emuDB(db_path, verbose = FALSE)
  bundles_db  <- list_bundles(kawahiva)$name
  novos       <- setdiff(novos_candidatos, bundles_db)
} else {
  novos       <- novos_candidatos
  kawahiva    <- NULL
}

cat(sprintf("📂 Arquivos no corpus: %d\n", length(novos_candidatos)))
cat(sprintf("✅ Já processados:     %d\n", length(novos_candidatos) - length(novos)))
cat(sprintf("🆕 Novos para processar: %d\n\n", length(novos)))

if (length(novos) == 0) {
  cat("✅ Corpus já está atualizado. Nada a fazer.\n")
  quit(save = "no")
}

cat("Novos arquivos:\n")
for (n in novos) cat(sprintf("  + %s\n", n))
cat("\n")

# ── 2. Copiar novos arquivos para a coleção temporária ───────
if (!dir.exists(COLECAO)) dir.create(COLECAO, recursive = TRUE)

for (nome in novos) {
  wav_src <- file.path(WAV_DIR, paste0(nome, ".wav"))
  tg_src  <- file.path(TG_DIR,  paste0(nome, ".TextGrid"))
  file.copy(wav_src, COLECAO, overwrite = TRUE)
  file.copy(tg_src,  COLECAO, overwrite = TRUE)
}
cat(sprintf("📋 %d pares copiados para coleção temporária.\n\n", length(novos)))

# ── 3. Criar ou atualizar o emuDB ────────────────────────────
if (is.null(kawahiva)) {
  cat("🏗️  Criando novo emuDB...\n")
  convert_TextGridCollection(
    dir       = COLECAO,
    dbName    = DB_NAME,
    targetDir = DB_DIR,
    verbose   = FALSE
  )
  kawahiva <- load_emuDB(db_path, verbose = FALSE)

  # Configurar trilhas na primeira execução
  cat("⚙️  Configurando trilhas de análise...\n")
  add_ssffTrackDefinition(kawahiva, name = "FORMANTS",
    onTheFlyFunctionName = "forest",
    onTheFlyParams = list(numFormants = 4, gender = "u"), verbose = FALSE)

  add_ssffTrackDefinition(kawahiva, name = "PITCH",
    onTheFlyFunctionName = "ksvF0",
    onTheFlyParams = list(minF = 50, maxF = 500), verbose = FALSE)

  add_ssffTrackDefinition(kawahiva, name = "RMS",
    onTheFlyFunctionName = "rmsana", verbose = FALSE)

  # Perspectivas
  set_signalCanvasesOrder(kawahiva, "default", c("OSCI", "SPEC"))
  set_levelCanvasesOrder(kawahiva,  "default", c("words", "phones"))

  add_perspective(kawahiva, "Formantes")
  set_signalCanvasesOrder(kawahiva, "Formantes", c("OSCI", "SPEC"))
  set_levelCanvasesOrder(kawahiva,  "Formantes", c("words", "phones"))

  add_perspective(kawahiva, "Pitch")
  set_signalCanvasesOrder(kawahiva, "Pitch", c("OSCI", "PITCH"))
  set_levelCanvasesOrder(kawahiva,  "Pitch", c("words", "phones"))

  add_perspective(kawahiva, "Completo")
  set_signalCanvasesOrder(kawahiva, "Completo", c("OSCI", "SPEC", "PITCH", "RMS"))
  set_levelCanvasesOrder(kawahiva,  "Completo", c("words", "phones"))

} else {
  cat("📥 Importando novos bundles para emuDB existente...\n")
  import_mediaFiles(kawahiva,
    dir     = COLECAO,
    session = "0000_ses",
    verbose = FALSE)
}

# ── 4. Calcular SSFF para os novos arquivos ──────────────────
cat("🔬 Calculando formantes, pitch e intensidade...\n")

for (nome in novos) {
  tryCatch({
    # Formantes
    forest(file.path(COLECAO, paste0(nome, ".wav")),
           toFile = TRUE, outputDirectory =
             file.path(db_path, "0000_ses", paste0(nome, "_bndl")))

    # Pitch
    ksvF0(file.path(COLECAO, paste0(nome, ".wav")),
          toFile = TRUE, outputDirectory =
            file.path(db_path, "0000_ses", paste0(nome, "_bndl")))

    # RMS
    rmsana(file.path(COLECAO, paste0(nome, ".wav")),
           toFile = TRUE, outputDirectory =
             file.path(db_path, "0000_ses", paste0(nome, "_bndl")))

    cat(sprintf("  ✅ %s\n", nome))
  }, error = function(e) {
    cat(sprintf("  ❌ Erro em %s: %s\n", nome, e$message))
  })
}

# ── 5. Limpar arquivos temporários ───────────────────────────
unlink(list.files(COLECAO, full.names = TRUE))
cat("\n🧹 Arquivos temporários removidos.\n")

# ── 6. Resumo final ──────────────────────────────────────────
bundles_final <- nrow(list_bundles(kawahiva))
cat(sprintf("\n════════════════════════════════════════\n"))
cat(sprintf(" ✅ Concluído! Total no corpus: %d itens\n", bundles_final))
cat(sprintf("════════════════════════════════════════\n"))
