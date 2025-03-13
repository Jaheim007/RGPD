# -*- coding: utf-8 -*-
"""
Exemple de Bot Telegram RGPD/ePrivacy multilingue (fr/en):
 - Détection de la langue de l'utilisateur dans Telegram (fr, en, fallback en)
 - Détection de la langue du site scanné (fr, en, fallback => combiner fr+en)
 - Score maximum = 100 si tout est conforme (HTTPS + Politique + Bandeau + Mentions Légales) 
   -10 si cookies sont détectés (déposés sans consentement)
 - Mise en page claire du PDF et du texte Telegram
 - Souligne que non-conformité => risques de violation de la vie privée, 
   compromission de données utilisateurs, pénalités et amendes
 - Avertissement supplémentaire : ce rapport est automatisé, peut contenir des erreurs
   et ne remplace pas une vérification manuelle par un expert.
"""

import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import requests
import os
import http.cookiejar
import urllib.request
import re
import datetime
from bs4 import BeautifulSoup
import pdfkit
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0  # Rendre langdetect déterministe

# ---------------------------------------------------------------------------
# ------------------------ Configuration du Bot Telegram ---------------------
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = "7907671010:AAEjesBsOXwpDaSyHatOTPzd7cRU62j6D3w"

# IMPORTANT : wkhtmltopdf doit être installé sur la machine
WKHTMLTOPDF_PATH = r"C:\\Users\\cococe ltd\\Downloads\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"

# ---------------------------------------------------------------------------
# -------------------------- Textes multilingues ----------------------------
# ---------------------------------------------------------------------------

messages = {
    "fr": {
        "analysis_name": "RGPD/ePrivacy",
        "welcome": (
            "👋 Bienvenue ! Cette analyse RGPD/ePrivacy vous aide à comprendre si un site "
            "protège réellement les données des utilisateurs et prend les mesures adéquates "
            "pour se conformer aux réglementations internationales. "
            "Un manque de conformité peut mener à une violation de la vie privée, à la "
            "compromission de données utilisateurs, ainsi qu'à de lourdes pénalités et amendes.\n\n"
            "Envoyez-moi simplement un ou plusieurs noms de domaines (séparés par des virgules)."
        ),
        "analysis_in_progress": "🔍 Analyse en cours pour : {} ...",
        "domain_inaccessible": "Site inaccessible",
        "pdf_caption": (
            "📄 Voici le rapport PDF.\n"
            "⚠️ Avertissement : Cette analyse RGPD/ePrivacy est automatisée. "
            "Elle ne remplace pas un audit complet ni l'avis d'un expert certifié. "
            "Consultez un DPO ou un expert juridique pour confirmer votre conformité."
        ),
        "no_domains": "⚠️ Veuillez entrer au moins un nom de domaine.",
        "pdf_error": "⚠️ Impossible de récupérer le rapport PDF.",
        # Rapport
        "report_title": "Rapport RGPD/ePrivacy",
        "report_header": "<h2>=== RAPPORT RGPD/ePrivacy ===</h2><p><i>Date : {}</i></p>",
        "report_intro": (
            "<p>Cette analyse vise à déterminer si les données des utilisateurs sont protégées, "
            "et si le site respecte le cadre RGPD/ePrivacy. Un manque de conformité "
            "peut exposer à de graves risques de violation de la vie privée, la compromission "
            "de données, et de lourdes sanctions pécuniaires.</p>"
            "<p><strong>Analyse demandée pour :</strong> {}</p>"
        ),
        "report_per_domain": (
            "<hr><h3>Résultats pour {}</h3>"
        ),
        "report_error": "<p><em>Erreur :</em> {}</p>",
        "report_details": (
            "<p><strong>Score RGPD/ePrivacy :</strong> {score}/100</p>"
            "<p><strong>Niveau de risque :</strong> {risk_level}</p>"
            "<p><strong>Recommandation :</strong> {risk_message}</p>"
            "<p><strong>HTTPS :</strong> {https_status}</p>"
            "<p><strong>Politique de confidentialité :</strong> {privacy}</p>"
            "<p><strong>Bandeau cookies :</strong> {cookie_banner}</p>"
            "<p><strong>Mentions légales :</strong> {legal}</p>"
            "<p><strong>Cookies détectés :</strong> {cookies_count}</p>"
            "<p><strong>Google Analytics :</strong> {ga}</p>"
            "<p><strong>Facebook Pixel :</strong> {fb}</p>"
            "<p><strong>Formulaire de contact :</strong> {form}</p>"
            "<p><strong>Trackers tiers :</strong> {trackers}</p>"
        ),
        "report_warning": (
            "<hr><p><strong>⚠️ Avertissement :</strong> Cette analyse RGPD/ePrivacy "
            "est une évaluation automatisée. Elle ne remplace pas un audit complet "
            "ni l'avis d'un expert certifié. Consultez un <strong>DPO</strong> ou "
            "un expert juridique pour confirmer votre conformité.</p>"
            "<p><em>De plus, ce rapport peut contenir des erreurs et ne couvre pas tous "
            "les aspects du RGPD/ePrivacy. Une vérification manuelle par un professionnel "
            "reste indispensable pour garantir la conformité.</em></p>"
        ),
        # Risques
        "risk_level": {
            "ok": "✅ Conforme",
            "medium": "⚠️ Risque Modéré",
            "high": "🛑 Risque Élevé",
            "critical": "🚨 Risque Critique",
        },
        "risk_message": {
            "ok": "Le site semble respecter le RGPD/ePrivacy. Continuez à surveiller les évolutions légales.",
            "medium": "Quelques éléments sont manquants. Vérifiez votre politique de confidentialité et votre bandeau cookies.",
            "high": "Votre site présente des manquements ! Ajoutez une politique de confidentialité et un bandeau cookies.",
            "critical": "Votre site n’est pas conforme. Vous risquez de lourdes sanctions ! Consultez un DPO.",
        },
        # Oui / Non
        "yes": "✅ Oui",
        "no": "❌ Non",
        # Mots-clés (exhaustifs)
        "privacy_keywords": [
            "politique de confidentialité", "vie privée", "protection des données",
            "données personnelles", "charte de confidentialité", "rgpd"
        ],
        "legal_keywords": [
            "mentions légales", "legal notice", "conditions générales", 
            "conditions d'utilisation", "cgu", "cgv"
        ],
        "cookie_keywords": [
            "cookie", "consent", "rgpd", "gdpr", "eprivacy", 
            "bandeau cookies", "traceurs", "consentement"
        ],
    },
    "en": {
        "analysis_name": "GDPR/ePrivacy",
        "welcome": (
            "👋 Welcome! This GDPR/ePrivacy analysis helps you see if a site truly "
            "protects user data and takes adequate measures to comply with international "
            "regulations. Non-compliance may lead to privacy violations, user data compromise, "
            "and heavy penalties or fines.\n\n"
            "Just send me one or more domain names (separated by commas)."
        ),
        "analysis_in_progress": "🔍 Analysis in progress for: {} ...",
        "domain_inaccessible": "Site inaccessible",
        "pdf_caption": (
            "📄 Here is the PDF report.\n"
            "⚠️ Warning: This GDPR/ePrivacy analysis is automated. "
            "It does not replace a full audit or expert advice. "
            "Consult a DPO or legal expert to confirm your compliance."
        ),
        "no_domains": "⚠️ Please enter at least one domain name.",
        "pdf_error": "⚠️ Unable to retrieve the PDF report.",
        # Report
        "report_title": "GDPR/ePrivacy Report",
        "report_header": "<h2>=== GDPR/ePrivacy REPORT ===</h2><p><i>Date: {}</i></p>",
        "report_intro": (
            "<p>This analysis aims to determine whether user data is protected and if the site "
            "respects GDPR/ePrivacy rules. Non-compliance may expose you to serious privacy "
            "risks, data compromise, and heavy fines.</p>"
            "<p><strong>Analysis requested for:</strong> {}</p>"
        ),
        "report_per_domain": (
            "<hr><h3>Results for {}</h3>"
        ),
        "report_error": "<p><em>Error:</em> {}</p>",
        "report_details": (
            "<p><strong>GDPR/ePrivacy Score:</strong> {score}/100</p>"
            "<p><strong>Risk Level:</strong> {risk_level}</p>"
            "<p><strong>Recommendation:</strong> {risk_message}</p>"
            "<p><strong>HTTPS:</strong> {https_status}</p>"
            "<p><strong>Privacy Policy:</strong> {privacy}</p>"
            "<p><strong>Cookie Banner:</strong> {cookie_banner}</p>"
            "<p><strong>Legal Mentions:</strong> {legal}</p>"
            "<p><strong>Cookies detected:</strong> {cookies_count}</p>"
            "<p><strong>Google Analytics:</strong> {ga}</p>"
            "<p><strong>Facebook Pixel:</strong> {fb}</p>"
            "<p><strong>Contact Form:</strong> {form}</p>"
            "<p><strong>Third-party Trackers:</strong> {trackers}</p>"
        ),
        "report_warning": (
            "<hr><p><strong>⚠️ Warning:</strong> This GDPR/ePrivacy analysis "
            "is automated. It does not replace a full compliance audit or professional "
            "legal advice. Please consult a <strong>DPO</strong> or a legal expert "
            "to confirm your compliance.</p>"
            "<p><em>Additionally, this report may contain errors and does not cover all "
            "aspects of GDPR/ePrivacy. A manual review by a professional remains essential "
            "to ensure compliance.</em></p>"
        ),
        # Risk
        "risk_level": {
            "ok": "✅ Compliant",
            "medium": "⚠️ Moderate Risk",
            "high": "🛑 High Risk",
            "critical": "🚨 Critical Risk",
        },
        "risk_message": {
            "ok": "The site appears GDPR/ePrivacy compliant. Keep monitoring legal changes.",
            "medium": "Some elements are missing. Check your privacy policy and cookie banner.",
            "high": "Your site has major gaps! Add a privacy policy and a cookie banner.",
            "critical": "Your site is not compliant. You risk significant fines! Consult a DPO.",
        },
        # Yes / No
        "yes": "✅ Yes",
        "no": "❌ No",
        # More exhaustive keywords
        "privacy_keywords": [
            "privacy policy", "privacy", "data protection", "personal data", 
            "gdpr policy", "data privacy"
        ],
        "legal_keywords": [
            "legal notice", "terms of service", "terms of use", 
            "imprint", "disclaimer"
        ],
        "cookie_keywords": [
            "cookie", "consent", "rgpd", "gdpr", "eprivacy", 
            "cookie banner", "trackers"
        ],
    },
}

# ---------------------------------------------------------------------------
# ------------------- Détection de la langue de l'utilisateur ----------------
# ---------------------------------------------------------------------------

def get_user_language(update):
    """
    Récupère la langue Telegram de l'utilisateur (ex: 'fr', 'en'...),
    renvoie 'fr' ou 'en' par défaut (fallback en).
    """
    user_lang = update.effective_user.language_code
    if not user_lang:
        return "en"
    user_lang = user_lang.lower()
    if user_lang.startswith("fr"):
        return "fr"
    else:
        return "en"

# ---------------------------------------------------------------------------
# -------------------- Détection de la langue du site -----------------------
# ---------------------------------------------------------------------------

def detect_site_language(html_content):
    """
    Détecte la langue (fr, en, ...) du contenu HTML en regardant :
    - <html lang="xx">
    - <meta http-equiv="content-language" ...>
    - Sinon, langdetect
    Retourne 'fr', 'en' ou 'other' si incertain
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Chercher l'attribut lang sur <html>
    html_tag = soup.find("html")
    if html_tag and html_tag.has_attr("lang"):
        possible_lang = html_tag["lang"].split("-")[0].lower()
        if possible_lang.startswith("fr"):
            return "fr"
        elif possible_lang.startswith("en"):
            return "en"

    # Chercher <meta http-equiv="content-language">
    meta_lang = soup.find("meta", attrs={"http-equiv": "content-language"})
    if meta_lang and meta_lang.has_attr("content"):
        possible_lang = meta_lang["content"].split("-")[0].lower()
        if possible_lang.startswith("fr"):
            return "fr"
        elif possible_lang.startswith("en"):
            return "en"

    # Essayer langdetect
    text_sample = soup.get_text(separator=" ", strip=True)
    if len(text_sample) > 1000:
        text_sample = text_sample[:1000]
    if text_sample:
        try:
            detected = detect(text_sample)
            if detected.startswith("fr"):
                return "fr"
            elif detected.startswith("en"):
                return "en"
        except:
            pass

    return "other"

# ---------------------------------------------------------------------------
# ------------------------ Fonctions d'analyse RGPD/ePrivacy ----------------
# ---------------------------------------------------------------------------

def format_domain(domain):
    """Force https si pas présent."""
    if not domain.startswith(("http://", "https://")):
        domain = "https://" + domain
    return domain

def check_https(url):
    return url.startswith("https://")

def get_website_content(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException:
        return None

def check_privacy_policy(html_content, site_lang):
    soup = BeautifulSoup(html_content, "html.parser")
    if site_lang in ["fr", "en"]:
        keywords = messages[site_lang]["privacy_keywords"]
    else:
        keywords = (messages["fr"]["privacy_keywords"] + messages["en"]["privacy_keywords"])

    for link in soup.find_all("a", href=True):
        link_text = link.text.lower()
        for kw in keywords:
            if kw in link_text:
                return link["href"]
    return None

def check_legal_mentions(html_content, site_lang):
    soup = BeautifulSoup(html_content, "html.parser")
    if site_lang in ["fr", "en"]:
        keywords = messages[site_lang]["legal_keywords"]
    else:
        keywords = (messages["fr"]["legal_keywords"] + messages["en"]["legal_keywords"])

    for link in soup.find_all("a", href=True):
        link_text = link.text.lower()
        for kw in keywords:
            if kw in link_text:
                return link["href"]
    return None

def check_cookie_banner(html_content, site_lang):
    soup = BeautifulSoup(html_content, "html.parser")
    if site_lang in ["fr", "en"]:
        keywords = messages[site_lang]["cookie_keywords"]
    else:
        keywords = (messages["fr"]["cookie_keywords"] + messages["en"]["cookie_keywords"])

    for element in soup.find_all(["script", "div"]):
        text_lower = element.text.lower()
        if any(kw in text_lower for kw in keywords):
            return True
    return False

def get_cookies(url):
    try:
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        opener.open(url)
        return [{"name": c.name, "domain": c.domain} for c in cj]
    except:
        return []

def detect_google_analytics(html_content):
    if "googletagmanager.com/gtag/js" in html_content or "google-analytics.com" in html_content:
        return True
    return False

def detect_facebook_pixel(html_content):
    if "connect.facebook.net" in html_content or "facebook_pixel" in html_content:
        return True
    return False

def detect_contact_form(html_content):
    if "<form" in html_content.lower():
        return True
    return False

def detect_third_party_trackers(html_content):
    trackers = {}
    known_trackers = {
        "DoubleClick": "doubleclick.net",
        "Hotjar": "static.hotjar.com",
    }
    html_lower = html_content.lower()
    for name, signature in known_trackers.items():
        if signature in html_lower:
            trackers[name] = True
    return trackers

# ---------------------------------------------------------------------------
# ---------------- Calcul du score (max 100) ---------------------------------
# ---------------------------------------------------------------------------

def calculate_gdpr_score(https_status, privacy_policy, cookie_banner, legal_mentions, cookies):
    """
    - HTTPS : +25
    - Politique de confidentialité : +25
    - Bandeau cookies : +25
    - Mentions légales : +25
    - Si le site dépose des cookies => -10
    Score max = 100 si tout est conforme et pas de cookie.
    """
    score = 0

    if https_status:
        score += 25
    if privacy_policy:
        score += 25
    if cookie_banner:
        score += 25
    if legal_mentions:
        score += 25

    # Pénalité si des cookies sont présents
    if cookies:
        score -= 10

    return max(score, 0)

def get_risk_level_and_msg(score, lang):
    if score >= 80:
        return (messages[lang]["risk_level"]["ok"], messages[lang]["risk_message"]["ok"])
    elif score >= 60:
        return (messages[lang]["risk_level"]["medium"], messages[lang]["risk_message"]["medium"])
    elif score >= 40:
        return (messages[lang]["risk_level"]["high"], messages[lang]["risk_message"]["high"])
    else:
        return (messages[lang]["risk_level"]["critical"], messages[lang]["risk_message"]["critical"])

# ---------------------------------------------------------------------------
# ---------------- Génération du PDF RGPD/ePrivacy --------------------------
# ---------------------------------------------------------------------------

def generate_gdpr_report(domains, results, user_lang):
    """
    Génère un PDF nommé en fonction de la langue et la date, ex:
    rgpd_eprivacy_report_YYYY-MM-DD_HH-MM.pdf (fr)
    gdpr_eprivacy_report_YYYY-MM-DD_HH-MM.pdf (en)
    """
    date_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    # Nom du fichier en fonction de la langue
    if user_lang == "fr":
        file_name = f"rgpd_eprivacy_report_{date_str}.pdf"
    else:
        file_name = f"gdpr_eprivacy_report_{date_str}.pdf"

    report_dir = "static/reports"
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)
    
    report_path = os.path.join(report_dir, file_name)

    # On construit un HTML complet
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = messages[user_lang]["report_header"].format(now_str)
    intro = messages[user_lang]["report_intro"].format(", ".join(domains))
    warning = messages[user_lang]["report_warning"]
    title = messages[user_lang]["report_title"]

    report_html = f"""<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
    body {{
        font-family: 'Segoe UI Emoji', 'Apple Color Emoji', 'Noto Color Emoji', Arial, sans-serif;
        margin: 40px;
    }}
    h2, h3 {{
        margin-bottom: 0.3em;
    }}
    p {{
        margin-top: 0.3em;
        margin-bottom: 0.9em;
    }}
    </style>
</head>
<body>
{header}
{intro}
"""

    for domain, data in results.items():
        report_html += messages[user_lang]["report_per_domain"].format(domain)
        if "error" in data:
            report_html += messages[user_lang]["report_error"].format(data["error"])
        else:
            risk_level, risk_message = get_risk_level_and_msg(data["gdpr_score"], user_lang)
            details_map = {
                "score": data["gdpr_score"],
                "risk_level": risk_level,
                "risk_message": risk_message,
                "https_status": messages[user_lang]["yes"] if data["https_status"] else messages[user_lang]["no"],
                "privacy": messages[user_lang]["yes"] if data["privacy_policy"] else messages[user_lang]["no"],
                "cookie_banner": messages[user_lang]["yes"] if data["cookie_banner"] else messages[user_lang]["no"],
                "legal": messages[user_lang]["yes"] if data["legal_mentions"] else messages[user_lang]["no"],
                "cookies_count": len(data["cookies"]),
                "ga": messages[user_lang]["yes"] if data["google_analytics"] else messages[user_lang]["no"],
                "fb": messages[user_lang]["yes"] if data["facebook_pixel"] else messages[user_lang]["no"],
                "form": messages[user_lang]["yes"] if data["contact_form"] else messages[user_lang]["no"],
                "trackers": ", ".join(data["third_party_trackers"].keys()) if data["third_party_trackers"] else "None",
            }
            report_html += messages[user_lang]["report_details"].format(**details_map)

    report_html += warning
    report_html += "</body></html>"

    config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
    pdfkit.from_string(report_html, report_path, configuration=config)

    return file_name, report_path

# ---------------------------------------------------------------------------
# ---------- Génération du texte à afficher directement dans Telegram -------
# ---------------------------------------------------------------------------

def format_report_text(domains, results, user_lang):
    """
    Génère un texte HTML à envoyer dans Telegram,
    avec la même structure que le PDF (balises <b>, <i>, etc.).
    """
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = messages[user_lang]["report_header"].format(now_str)
    intro = messages[user_lang]["report_intro"].format(", ".join(domains))
    warning = messages[user_lang]["report_warning"]

    # Remplacez les balises <h2>, <h3>, <p> par du HTML plus léger pour Telegram
    text = (f"<b>=== {messages[user_lang]['analysis_name']} ===</b>\n"
            f"<i>Date : {now_str}</i>\n\n") if user_lang == "fr" else (
            f"<b>=== {messages[user_lang]['analysis_name']} REPORT ===</b>\n"
            f"<i>Date: {now_str}</i>\n\n")

    soup_intro = BeautifulSoup(intro, "html.parser")
    text += soup_intro.get_text("\n") + "\n"

    for domain, data in results.items():
        text += "----------------------------------------\n"
        text += (f"<b>Résultats pour {domain} :</b>\n" if user_lang == "fr" 
                 else f"<b>Results for {domain}:</b>\n")
        if "error" in data:
            text += f"<i>{data['error']}</i>\n"
        else:
            risk_level, risk_message = get_risk_level_and_msg(data["gdpr_score"], user_lang)
            text += (f"• <b>Score RGPD/ePrivacy :</b> {data['gdpr_score']}/100\n"
                     if user_lang == "fr" else
                     f"• <b>GDPR/ePrivacy Score:</b> {data['gdpr_score']}/100\n")
            text += f"• <b>{'Niveau de risque' if user_lang=='fr' else 'Risk Level'}:</b> {risk_level}\n"
            text += f"• <b>{'Recommandation' if user_lang=='fr' else 'Recommendation'}:</b> {risk_message}\n"
            https_str = messages[user_lang]["yes"] if data["https_status"] else messages[user_lang]["no"]
            text += f"• HTTPS: {https_str}\n"
            privacy_str = messages[user_lang]["yes"] if data["privacy_policy"] else messages[user_lang]["no"]
            text += (f"• Politique de confidentialité: {privacy_str}\n" if user_lang=="fr"
                     else f"• Privacy Policy: {privacy_str}\n")
            cookie_str = messages[user_lang]["yes"] if data["cookie_banner"] else messages[user_lang]["no"]
            text += (f"• Bandeau cookies: {cookie_str}\n" if user_lang=="fr"
                     else f"• Cookie Banner: {cookie_str}\n")
            legal_str = messages[user_lang]["yes"] if data["legal_mentions"] else messages[user_lang]["no"]
            text += (f"• Mentions légales: {legal_str}\n" if user_lang=="fr"
                     else f"• Legal Mentions: {legal_str}\n")
            text += (f"• Cookies détectés: {len(data['cookies'])}\n" if user_lang=="fr"
                     else f"• Cookies detected: {len(data['cookies'])}\n")
            ga_str = messages[user_lang]["yes"] if data["google_analytics"] else messages[user_lang]["no"]
            text += f"• Google Analytics: {ga_str}\n"
            fb_str = messages[user_lang]["yes"] if data["facebook_pixel"] else messages[user_lang]["no"]
            text += f"• Facebook Pixel: {fb_str}\n"
            form_str = messages[user_lang]["yes"] if data["contact_form"] else messages[user_lang]["no"]
            text += (f"• Formulaire de contact: {form_str}\n" if user_lang=="fr"
                     else f"• Contact Form: {form_str}\n")
            trackers = ", ".join(data["third_party_trackers"].keys()) if data["third_party_trackers"] else "None"
            text += (f"• Trackers tiers: {trackers}\n" if user_lang=="fr"
                     else f"• Third-party Trackers: {trackers}\n")

        text += "\n"

    # Ajout de l'avertissement final
    soup_warn = BeautifulSoup(warning, "html.parser")
    text_warning = soup_warn.get_text("\n")
    text += "----------------------------------------\n"
    text += text_warning
    return text

# ---------------------------------------------------------------------------
# -------------------------- Fonctions du Bot Telegram -----------------------
# ---------------------------------------------------------------------------

def start(update, context):
    user_lang = get_user_language(update)
    update.message.reply_text(messages[user_lang]["welcome"])

def scan_domains(update, context):
    user_lang = get_user_language(update)
    text_msg = update.message.text.strip()
    domains = [d.strip() for d in text_msg.split(",") if d.strip()]

    if not domains:
        update.message.reply_text(messages[user_lang]["no_domains"])
        return

    # On informe qu'on analyse
    update.message.reply_text(messages[user_lang]["analysis_in_progress"].format(", ".join(domains)))

    results = {}
    for domain in domains:
        url = format_domain(domain)
        html = get_website_content(url)
        if not html:
            results[domain] = {"error": messages[user_lang]["domain_inaccessible"]}
            continue

        # Détecter la langue du site
        site_lang = detect_site_language(html)

        # Check
        https_status = check_https(url)
        privacy_policy = check_privacy_policy(html, site_lang)
        cookie_banner = check_cookie_banner(html, site_lang)
        legal_mentions = check_legal_mentions(html, site_lang)
        cookies_list = get_cookies(url)

        gdpr_score = calculate_gdpr_score(
            https_status,
            privacy_policy,
            cookie_banner,
            legal_mentions,
            cookies_list
        )

        # Détections supplémentaires
        google_analytics = detect_google_analytics(html)
        facebook_pixel = detect_facebook_pixel(html)
        contact_form = detect_contact_form(html)
        third_party_trackers = detect_third_party_trackers(html)

        results[domain] = {
            "https_status": https_status,
            "privacy_policy": privacy_policy,
            "cookie_banner": cookie_banner,
            "legal_mentions": legal_mentions,
            "cookies": cookies_list,
            "gdpr_score": gdpr_score,
            "google_analytics": google_analytics,
            "facebook_pixel": facebook_pixel,
            "contact_form": contact_form,
            "third_party_trackers": third_party_trackers,
        }

    # Génération du PDF
    pdf_name, pdf_path = generate_gdpr_report(domains, results, user_lang)
    # Texte complet
    report_text = format_report_text(domains, results, user_lang)
    update.message.reply_text(report_text, parse_mode="HTML")

    # Envoi du PDF
    if os.path.exists(pdf_path):
        update.message.reply_document(open(pdf_path, "rb"), caption=messages[user_lang]["pdf_caption"])
    else:
        update.message.reply_text(messages[user_lang]["pdf_error"])

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, scan_domains))

    updater.start_polling()
    updater.idle()

# ---------------------------------------------------------------------------
# ------------------------- Point d'entrée principal -------------------------
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
