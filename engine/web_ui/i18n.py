"""
Tiny translation helper for the dashboard UI (English / Spanish).

Scope: dashboard chrome only — buttons, labels, help text, status messages.
AI-generated content (tweets, video scripts, captions) is NOT translated by
this module; those stay in whatever language script_generator.py produces.

Usage:
    from i18n import t, LANGS
    st.title(t("app_title"))
    st.caption(t("app_caption", day=5))
"""
import streamlit as st

LANGS = {"English": "en", "Español": "es"}

T: dict[str, dict[str, str]] = {
    # ── Page header ──────────────────────────────────────────────
    "app_title": {
        "en": "EPIFANI AI — Growth Engine",
        "es": "EPIFANI AI — Motor de Crecimiento",
    },
    "app_caption": {
        "en": "Day {day} of building Epifani · Preview, manage, and trigger daily content publishing",
        "es": "Día {day} construyendo Epifani · Previsualizá, gestioná y publicá el contenido diario",
    },

    # ── Sidebar: settings ────────────────────────────────────────
    "lang_label": {"en": "🌐 Language", "es": "🌐 Idioma"},
    "settings_header": {"en": "⚙️ Settings", "es": "⚙️ Configuración"},
    "max_picks_label": {"en": "Max picks to post", "es": "Máximo de picks a publicar"},
    "platforms_header": {"en": "📡 Platforms", "es": "📡 Plataformas"},
    "dry_run_label": {"en": "Dry run (no actual posting)", "es": "Modo de prueba (no publica nada real)"},
    "dry_run_info": {
        "en": "Dry run ON — nothing will be posted",
        "es": "Modo de prueba ACTIVADO — no se publicará nada",
    },
    "exclude_markets_header": {"en": "🎯 Exclude Markets", "es": "🎯 Excluir Mercados"},
    "filters_header": {"en": "📊 Filters", "es": "📊 Filtros"},
    "value_only_label": {"en": "Value bets only", "es": "Solo apuestas de valor"},
    "value_only_help": {
        "en": "ON = only show picks where odds imply value (is_value=true). Turn OFF to see all picks above confidence threshold.",
        "es": "ACTIVADO = solo muestra picks donde la cuota implica valor (is_value=true). Desactivalo para ver todos los picks por encima del umbral de confianza.",
    },
    "credentials_header": {"en": "🔧 Credentials", "es": "🔧 Credenciales"},
    "cred_ok": {"en": "✓ {name}", "es": "✓ {name}"},
    "cred_missing": {"en": "✗ {name} — add keys to .env", "es": "✗ {name} — agregá las claves en .env"},
    "scheduler_header": {"en": "🕐 Scheduler", "es": "🕐 Programador"},
    "scheduler_running": {"en": "Running (PID {pid})", "es": "En ejecución (PID {pid})"},
    "scheduler_stop_btn": {"en": "Stop scheduler", "es": "Detener programador"},
    "scheduler_not_running": {"en": "Not running", "es": "Detenido"},
    "scheduler_start_btn": {"en": "Start scheduler", "es": "Iniciar programador"},

    # ── Picks table ──────────────────────────────────────────────
    "no_picks_info": {
        "en": "No qualifying picks right now — you can still create a Founder's Journey video below (it will narrate the build without a pick). Start the portal or loosen the sidebar filters to include picks.",
        "es": "No hay picks que califiquen ahora mismo — igual podés crear un video de Founder's Journey más abajo (narrará el proceso sin un pick). Iniciá el portal o relajá los filtros de la barra lateral para incluir picks.",
    },
    "picks_header": {"en": "Today's Top {n} Picks", "es": "Los {n} Mejores Picks de Hoy"},
    "picks_caption": {
        "en": "Uncheck any pick you don't want to include before publishing.",
        "es": "Desmarcá cualquier pick que no quieras incluir antes de publicar.",
    },
    "col_match": {"en": "Match", "es": "Partido"},
    "col_pick": {"en": "Pick", "es": "Pick"},
    "col_odds": {"en": "Odds", "es": "Cuota"},
    "col_confidence": {"en": "Confidence", "es": "Confianza"},
    "col_edge": {"en": "Edge", "es": "Valor"},
    "col_tier": {"en": "Tier", "es": "Nivel"},
    "refresh_picks_btn": {"en": "🔄 Refresh Picks", "es": "🔄 Actualizar Picks"},
    "excluded_caption": {
        "en": "{excluded} pick(s) excluded — {active} will be published.",
        "es": "{excluded} pick(s) excluido(s) — se publicarán {active}.",
    },
    "all_selected_caption": {"en": "All {n} picks selected.", "es": "Los {n} picks están seleccionados."},

    # ── Founder's Journey ────────────────────────────────────────
    "journey_header": {"en": "✍️ Founder's Journey — Day {day}", "es": "✍️ Founder's Journey — Día {day}"},
    "journey_text_label": {
        "en": "What did you work on today? (e.g. 'Spent all night debugging our Portuguese league parser' or 'Connected the new live sports score API')",
        "es": "¿En qué trabajaste hoy? (ej: 'Pasé toda la noche debugueando el parser de la liga portuguesa' o 'Conecté la nueva API de resultados en vivo')",
    },
    "journey_text_placeholder": {
        "en": "Write a brief, informal update about your coding/building journey today...",
        "es": "Escribí una actualización breve e informal sobre tu jornada de programación de hoy...",
    },
    "journey_text_help": {
        "en": "Drives the first-person 'Day X of building Epifani' video script.",
        "es": "Impulsa el guion del video en primera persona 'Día X construyendo Epifani'.",
    },
    "voice_elevenlabs": {"en": "🎙️ Voice: **ElevenLabs** (emotional)", "es": "🎙️ Voz: **ElevenLabs** (emocional)"},
    "voice_edge_needs_key": {
        "en": "🎙️ Voice: **Edge-TTS** (robotic) — add `ELEVENLABS_API_KEY` to .env",
        "es": "🎙️ Voz: **Edge-TTS** (robótica) — agregá `ELEVENLABS_API_KEY` en .env",
    },
    "voice_edge": {"en": "🎙️ Voice: Edge-TTS", "es": "🎙️ Voz: Edge-TTS"},
    "avatar_yours": {"en": "🧑‍💻 Avatar: **your art** ({poses})", "es": "🧑‍💻 Avatar: **tu diseño** ({poses})"},
    "avatar_placeholder": {
        "en": "🧑‍💻 Avatar: **placeholder** — drop `character_closed.png` in assets/character/",
        "es": "🧑‍💻 Avatar: **de prueba** — colocá `character_closed.png` en assets/character/",
    },
    "avatar_none": {"en": "🧑‍💻 Avatar: none", "es": "🧑‍💻 Avatar: ninguno"},
    "cta_label": {"en": "Ending CTA", "es": "CTA final"},
    "cta_site": {"en": "🌐 Site link — epifanii.com", "es": "🌐 Link al sitio — epifanii.com"},
    "cta_comment": {
        "en": "💬 Comment-gate — “comment {word}” → you DM the model's output",
        "es": "💬 Comentario-gate — “comentá {word}” → le mandás por DM el resultado del modelo",
    },
    "cta_help": {
        "en": "Comment-gate is the growth mechanic from the niche research: comments feed the algorithm, the DM converts to a follower, and it sidesteps link suppression. You reply to the comments by DM (manually, or ManyChat on Instagram). TikTok/IG captions carry the gate; YouTube/X captions keep the site link.",
        "es": "El comentario-gate es la mecánica de crecimiento de la investigación de nicho: los comentarios alimentan el algoritmo, el DM convierte en seguidor, y evita la supresión de links. Respondés los comentarios por DM (manualmente, o con ManyChat en Instagram). Los captions de TikTok/IG usan el gate; los de YouTube/X mantienen el link al sitio.",
    },
    "gen_journey_btn": {"en": "🎬 Generate Journey Script", "es": "🎬 Generar Guion del Journey"},
    "gen_track_btn": {"en": "📈 Generate Track Record", "es": "📈 Generar Historial de Resultados"},
    "journey_vs_track_caption": {
        "en": "**Journey** weaves your milestone + picks. **Track Record** flexes the model's live stats (hit-rate/edge) as proof. Both run the writer → critic → rewriter loop (Gemini) with the no-betting-language guardrails.",
        "es": "**Journey** combina tu hito del día + los picks. **Track Record** muestra las estadísticas en vivo del modelo (aciertos/valor) como prueba. Ambos corren el ciclo escritor → crítico → reescritura (Gemini) con las reglas para evitar lenguaje de apuestas.",
    },
    "warn_write_milestone": {"en": "Write today's milestone above first.", "es": "Escribí primero el hito de hoy arriba."},
    "spinner_writing": {"en": "Writing and self-critiquing the script...", "es": "Escribiendo y autocriticando el guion..."},
    "err_journey_failed": {"en": "Journey script failed: {e}", "es": "Falló el guion del journey: {e}"},
    "spinner_track": {
        "en": "Pulling the model's live track record and writing...",
        "es": "Obteniendo el historial en vivo del modelo y escribiendo...",
    },
    "warn_no_perf": {
        "en": "No model performance data available from the portal yet.",
        "es": "Todavía no hay datos de rendimiento del modelo desde el portal.",
    },
    "success_track": {
        "en": "Track Record script ready — {hr}% over {sample} picks.",
        "es": "Guion de Track Record listo — {hr}% en {sample} picks.",
    },
    "err_track_failed": {"en": "Track record script failed: {e}", "es": "Falló el guion del track record: {e}"},
    "critic_score_label": {"en": "Critic Score", "es": "Puntaje del Crítico"},
    "rewrites_label": {"en": "Rewrites", "es": "Reescrituras"},
    "est_length_label": {"en": "Est. Length", "es": "Duración est."},
    "critic_notes_prefix": {"en": "Critic: {notes}", "es": "Crítico: {notes}"},
    "edit_script_caption": {
        "en": "✏️ Edit the script below before building — this is *your* founder voice, tweak it freely.",
        "es": "✏️ Editá el guion abajo antes de generar el video — es *tu* voz como founder, ajustalo libremente.",
    },
    "voiceover_label": {"en": "🎙️ Voiceover (spoken)", "es": "🎙️ Locución (hablada)"},
    "caption_label": {"en": "📝 Caption", "es": "📝 Descripción"},
    "hashtags_label": {"en": "#️⃣ Hashtags", "es": "#️⃣ Hashtags"},
    "platform_captions_expander": {
        "en": "🌐 Per-platform captions (TikTok · Instagram · YouTube · X)",
        "es": "🌐 Descripciones por plataforma (TikTok · Instagram · YouTube · X)",
    },
    "platform_captions_caption": {
        "en": "Native caption + hashtag variant for each platform, from your current caption. Compliance-safe (no betting language). One Gemini call.",
        "es": "Variante nativa de descripción + hashtags para cada plataforma, a partir de tu descripción actual. Cumple las normas (sin lenguaje de apuestas). Una sola llamada a Gemini.",
    },
    "gen_platform_captions_btn": {"en": "✨ Generate per-platform captions", "es": "✨ Generar descripciones por plataforma"},
    "spinner_platform_captions": {"en": "Tailoring captions per platform...", "es": "Adaptando descripciones por plataforma..."},
    "err_platform_captions": {"en": "Per-platform captions failed: {e}", "es": "Fallaron las descripciones por plataforma: {e}"},
    "visual_inserts_header": {
        "en": "**🖼️ Visual inserts** *(optional)* — pop a code card or image into the upper-right while you talk about it",
        "es": "**🖼️ Inserciones visuales** *(opcional)* — mostrá una tarjeta de código o imagen arriba a la derecha mientras hablás de eso",
    },
    "insert_expander_title": {"en": "Insert #{iid}", "es": "Inserción #{iid}"},
    "insert_ai_hint": {"en": "💡 AI suggestion: {hint}", "es": "💡 Sugerencia de la IA: {hint}"},
    "insert_type_label": {"en": "Type", "es": "Tipo"},
    "insert_type_code": {"en": "Code snippet", "es": "Fragmento de código"},
    "insert_type_image": {"en": "Library image", "es": "Imagen de biblioteca"},
    "insert_code_label": {"en": "Code (keep it ~4–8 short lines)", "es": "Código (mantenelo en ~4–8 líneas cortas)"},
    "insert_title_label": {"en": "Title (title-bar filename)", "es": "Título (nombre en la barra de título)"},
    "insert_lang_label": {"en": "Language", "es": "Lenguaje"},
    "insert_image_text_label": {"en": "Image path or library id", "es": "Ruta de imagen o id de biblioteca"},
    "insert_at_label": {"en": "Show at — a spoken phrase, or seconds", "es": "Mostrar en — una frase hablada, o segundos"},
    "insert_at_placeholder": {
        "en": "the function I built today   —or—   5.0",
        "es": "la función que armé hoy   —o—   5.0",
    },
    "insert_secs_label": {"en": "Secs", "es": "Seg"},
    "insert_remove_btn": {"en": "🗑 Remove", "es": "🗑 Quitar"},
    "add_insert_btn": {"en": "➕ Add insert", "es": "➕ Agregar inserción"},
    "suggest_inserts_btn": {"en": "✨ Suggest inserts (AI)", "es": "✨ Sugerir inserciones (IA)"},
    "suggest_inserts_help": {
        "en": "Gemini reads your voiceover and proposes where a code card / screenshot / diagram would help.",
        "es": "Gemini lee tu locución y propone dónde ayudaría una tarjeta de código / captura / diagrama.",
    },
    "spinner_suggest": {
        "en": "Scanning the voiceover for good visual moments...",
        "es": "Analizando la locución en busca de buenos momentos visuales...",
    },
    "err_suggest_failed": {"en": "Suggestion failed: {e}", "es": "Falló la sugerencia: {e}"},
    "info_no_suggestions": {
        "en": "No visual moments suggested (or the Gemini quota is used up).",
        "es": "No se sugirieron momentos visuales (o se agotó la cuota de Gemini).",
    },
    "success_inserts_added": {
        "en": "Added {n} suggested insert(s) — fill in the code/image and tweak.",
        "es": "Se agregaron {n} inserción(es) sugerida(s) — completá el código/imagen y ajustá.",
    },
    "build_journey_video_btn": {"en": "🎥 Build Journey Video", "es": "🎥 Generar Video del Journey"},
    "inserts_added_caption": {"en": "Adding {n} visual insert(s).", "es": "Agregando {n} inserción(es) visual(es)."},
    "spinner_render": {
        "en": "Rendering locally (voiceover → background → character → inserts → captions)...",
        "es": "Renderizando localmente (locución → fondo → personaje → inserciones → subtítulos)...",
    },
    "success_video_ready": {"en": "Journey video ready: {path}", "es": "Video del journey listo: {path}"},
    "err_video_build": {"en": "Video build failed: {error}", "es": "Falló la generación del video: {error}"},

    # ── Run Full Pipeline ────────────────────────────────────────
    "pipeline_header": {"en": "⚡ Run Full Pipeline", "es": "⚡ Ejecutar Pipeline Completo"},
    "pipeline_caption": {
        "en": "Generates cards + tweet threads + videos, then posts to all enabled platforms in one click.",
        "es": "Genera tarjetas + hilos de tweets + videos, y publica en todas las plataformas activadas con un solo clic.",
    },
    "publish_btn": {"en": "🚀 Publish Today's Picks", "es": "🚀 Publicar los Picks de Hoy"},
    "warn_no_picks_selected": {"en": "No picks selected.", "es": "No hay picks seleccionados."},
    "info_dry_run_pipeline": {
        "en": "Dry run is ON — pipeline will run but nothing will be posted.",
        "es": "El modo de prueba está ACTIVADO — el pipeline correrá pero no se publicará nada.",
    },
    "will_post_caption": {"en": "Will post {n} pick(s) to: {platforms}", "es": "Se publicarán {n} pick(s) en: {platforms}"},
    "no_platforms": {"en": "no platforms selected", "es": "no hay plataformas seleccionadas"},
    "err_no_picks_checked": {
        "en": "No picks selected. Check at least one pick above.",
        "es": "No hay picks seleccionados. Marcá al menos un pick arriba.",
    },
    "progress_start": {"en": "Starting...", "es": "Iniciando..."},
    "progress_cards": {"en": "Building cards...", "es": "Generando tarjetas..."},
    "progress_threads": {"en": "Generating tweet threads (Gemini)...", "es": "Generando hilos de tweets (Gemini)..."},
    "progress_videos": {
        "en": "Building videos (MPT) — this takes a few minutes...",
        "es": "Generando videos (MPT) — esto tarda unos minutos...",
    },
    "progress_twitter": {"en": "Posting to Twitter/X...", "es": "Publicando en Twitter/X..."},
    "success_twitter": {"en": "Twitter: posted {ok}/{total} thread(s)", "es": "Twitter: publicados {ok}/{total} hilo(s)"},
    "progress_social": {"en": "Posting videos to TikTok + Instagram...", "es": "Publicando videos en TikTok + Instagram..."},
    "success_social": {
        "en": "TikTok/Instagram: uploaded {ok}/{total} video(s)",
        "es": "TikTok/Instagram: subidos {ok}/{total} video(s)",
    },
    "progress_youtube": {"en": "Posting to YouTube Shorts...", "es": "Publicando en YouTube Shorts..."},
    "success_youtube": {
        "en": "YouTube Shorts: uploaded {ok}/{total} Shorts",
        "es": "YouTube Shorts: subidos {ok}/{total} Shorts",
    },
    "progress_done": {"en": "Done!", "es": "¡Listo!"},
    "err_pipeline_failed": {"en": "Pipeline failed: {e}", "es": "Falló el pipeline: {e}"},

    # ── Advanced / manual controls ───────────────────────────────
    "advanced_title": {
        "en": "🛠️ Advanced — manual step-by-step controls",
        "es": "🛠️ Avanzado — controles manuales paso a paso",
    },
    "advanced_caption": {
        "en": "Only needed if you want to run or re-run one step on its own (e.g. re-post just the videos). The '🚀 Publish Today's Picks' button above already does all of this in one click.",
        "es": "Solo hace falta si querés correr o repetir un paso por separado (ej: volver a publicar solo los videos). El botón '🚀 Publicar los Picks de Hoy' de arriba ya hace todo esto con un solo clic.",
    },
    "card_preview_header": {"en": "🖼️ Card Preview", "es": "🖼️ Vista Previa de Tarjetas"},
    "generate_cards_btn": {"en": "Generate Cards", "es": "Generar Tarjetas"},
    "success_cards_built": {"en": "Built {n} card sets", "es": "Se generaron {n} juegos de tarjetas"},
    "thread_preview_header": {"en": "✍️ Tweet Thread Preview", "es": "✍️ Vista Previa de Hilos de Tweets"},
    "generate_threads_btn": {"en": "Generate Tweet Threads (Gemini)", "es": "Generar Hilos de Tweets (Gemini)"},
    "spinner_gemini": {"en": "Calling Gemini...", "es": "Llamando a Gemini..."},
    "err_gemini_failed": {"en": "Gemini failed: {e}", "es": "Falló Gemini: {e}"},
    "thread_tweet1": {"en": "**Tweet 1 (Hook + Image)**\n\n{text}", "es": "**Tweet 1 (Gancho + Imagen)**\n\n{text}"},
    "thread_tweet2": {"en": "**Tweet 2 (Stats)**\n\n{text}", "es": "**Tweet 2 (Estadísticas)**\n\n{text}"},
    "thread_tweet3": {"en": "**Tweet 3 (CTA)**\n\n{text}", "es": "**Tweet 3 (CTA)**\n\n{text}"},
    "video_build_header": {"en": "🎬 Build Videos (MPT)", "es": "🎬 Generar Videos (MPT)"},
    "build_videos_btn": {"en": "Build Videos via MoneyPrinterTurbo", "es": "Generar Videos vía MoneyPrinterTurbo"},
    "spinner_build_videos": {
        "en": "Starting MPT and generating videos — this takes a few minutes...",
        "es": "Iniciando MPT y generando videos — esto tarda unos minutos...",
    },
    "success_videos_built": {"en": "Built {n} video(s)", "es": "Se generaron {n} video(s)"},
    "err_video_build_full": {"en": "Video build failed: {e}", "es": "Falló la generación de video: {e}"},
    "videos_ready_caption": {"en": "{n} video(s) ready: {matches}", "es": "{n} video(s) listos: {matches}"},
    "publish_header": {"en": "🚀 Publish", "es": "🚀 Publicar"},
    "post_twitter_btn": {"en": "Post to Twitter / X", "es": "Publicar en Twitter / X"},
    "warn_gen_cards_first": {"en": "Generate cards first", "es": "Generá las tarjetas primero"},
    "warn_gen_threads_first": {"en": "Generate tweet threads first", "es": "Generá los hilos de tweets primero"},
    "spinner_posting": {"en": "Posting...", "es": "Publicando..."},
    "success_threads_posted": {"en": "Posted {n} thread(s)", "es": "Se publicaron {n} hilo(s)"},
    "post_social_btn": {"en": "Post Videos to TikTok + Instagram", "es": "Publicar Videos en TikTok + Instagram"},
    "err_upload_post_not_configured": {
        "en": "Upload-Post not configured. Add UPLOAD_POST_API_KEY and UPLOAD_POST_USERNAME to .env",
        "es": "Upload-Post no está configurado. Agregá UPLOAD_POST_API_KEY y UPLOAD_POST_USERNAME en .env",
    },
    "warn_no_video_for": {
        "en": "No video for {match} — use 'Build Videos' above first",
        "es": "No hay video para {match} — usá 'Generar Videos' arriba primero",
    },
    "success_social_uploaded": {"en": "Uploaded {ok}/{n} video(s)", "es": "Se subieron {ok}/{n} video(s)"},
    "post_youtube_btn": {"en": "Post to YouTube Shorts", "es": "Publicar en YouTube Shorts"},
    "err_youtube_not_configured": {
        "en": "YouTube not configured. Add YOUTUBE_REFRESH_TOKEN to .env",
        "es": "YouTube no está configurado. Agregá YOUTUBE_REFRESH_TOKEN en .env",
    },
    "spinner_youtube_upload": {"en": "Uploading to YouTube...", "es": "Subiendo a YouTube..."},
    "success_youtube_uploaded": {"en": "Uploaded {ok}/{n} Shorts", "es": "Se subieron {ok}/{n} Shorts"},

    # ── Analytics ─────────────────────────────────────────────────
    "analytics_header": {"en": "📊 Analytics", "es": "📊 Estadísticas"},
    "metric_total_posted": {"en": "Total Posted", "es": "Total Publicado"},
    "metric_days_active": {"en": "Days Active", "es": "Días Activos"},
    "metric_wins": {"en": "Wins", "es": "Ganadas"},
    "metric_losses": {"en": "Losses", "es": "Perdidas"},
    "metric_avg_conf": {"en": "Avg Confidence", "es": "Confianza Prom."},
    "last_7_days": {"en": "**Last 7 days**", "es": "**Últimos 7 días**"},
    "no_posts_logged": {
        "en": "No posts logged yet. Data appears here after the first live run.",
        "es": "Todavía no hay publicaciones registradas. Los datos aparecen acá después de la primera corrida real.",
    },
    "recent_posts_expander": {"en": "Recent posts (last 30 days)", "es": "Publicaciones recientes (últimos 30 días)"},
    "nothing_yet": {"en": "Nothing yet.", "es": "Todavía nada."},
    "log_result_header": {"en": "**Log match result**", "es": "**Registrar resultado del partido**"},
    "pick_to_update_label": {"en": "Pick to update", "es": "Pick a actualizar"},
    "result_label": {"en": "Result", "es": "Resultado"},
    "result_win": {"en": "win", "es": "Ganada"},
    "result_loss": {"en": "loss", "es": "Perdida"},
    "result_void": {"en": "void", "es": "Anulada"},
    "save_result_btn": {"en": "Save result", "es": "Guardar resultado"},
    "success_result_saved": {"en": "Saved: {match} → {outcome}", "es": "Guardado: {match} → {outcome}"},
    "no_unresolved_caption": {
        "en": "No unresolved picks in the last 14 days.",
        "es": "No hay picks sin resolver en los últimos 14 días.",
    },
    "weekly_cols": {
        "en": "Date,Platform,Posted,Wins,Losses,Avg Conf %,Avg Edge %",
        "es": "Fecha,Plataforma,Publicados,Ganadas,Perdidas,Conf. Prom %,Valor Prom %",
    },
    "recent_cols": {
        "en": "Date,Platform,Match,Pick,Odds,Conf %,Edge %,Result",
        "es": "Fecha,Plataforma,Partido,Pick,Cuota,Conf %,Valor %,Resultado",
    },

    # ── Footer ────────────────────────────────────────────────────
    "footer_stopped": {"en": "Stopped", "es": "Detenido"},
    "footer_text": {
        "en": "Scheduler: {status} | Daily: 08:50 fetch → 09:00 Twitter → 09:10 videos | Timezone: Europe/Athens | Top {n} picks",
        "es": "Programador: {status} | Diario: 08:50 búsqueda → 09:00 Twitter → 09:10 videos | Zona horaria: Europe/Athens | Top {n} picks",
    },
}


def t(key: str, **kwargs) -> str:
    lang = st.session_state.get("lang", "en")
    entry = T.get(key)
    template = (entry.get(lang) or entry.get("en")) if entry else key
    return template.format(**kwargs) if kwargs else template
