"""Monitor de ingressos Bailacci no Bileto (Sympla).

Abre https://bileto.sympla.com.br/, busca "Bailacci" no campo de busca e,
se aparecer algum evento, envia push para o celular via ntfy.sh.
Sinaliza ao workflow para se desligar quando encontrar ou quando o dia acabar.
"""
import os
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

URL = "https://bileto.sympla.com.br/"
TERMO = "Bailacci"
TZ = ZoneInfo("America/Sao_Paulo")
PRAZO = datetime(2026, 10, 3, 23, 59, tzinfo=TZ)  # fim do dia de hoje
NTFY_TOPIC = os.environ["NTFY_TOPIC"]


def sinalizar_parada():
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write("stop=true\n")


def notificar(titulo, mensagem, link=URL):
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=mensagem.encode("utf-8"),
        headers={"Title": titulo, "Priority": "high", "Tags": "tada", "Click": link},
    )
    urllib.request.urlopen(req, timeout=20)


def buscar():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="pt-BR")
        page.goto(URL, wait_until="networkidle", timeout=60000)

        campo = page.locator(
            "input[type='search'], input[placeholder*='usca' i], "
            "input[placeholder*='esquis' i], input[name*='search' i]"
        ).first
        campo.wait_for(state="visible", timeout=30000)
        campo.fill(TERMO)
        campo.press("Enter")
        page.wait_for_load_state("networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        page.screenshot(path="resultado.png", full_page=True)

        # Resultados = links/cartões que contenham o termo (ignora o próprio campo)
        resultados = page.locator(f"a:has-text('{TERMO}')")
        achados = []
        for i in range(resultados.count()):
            el = resultados.nth(i)
            achados.append((el.inner_text().strip(), el.get_attribute("href") or URL))
        browser.close()
        return achados


def main():
    agora = datetime.now(TZ)
    if agora > PRAZO:
        print("Fim do dia: encerrando monitor.")
        sinalizar_parada()
        return

    achados = buscar()
    if achados:
        nome, href = achados[0]
        link = href if href.startswith("http") else URL.rstrip("/") + href
        notificar(
            "Ingressos Bailacci à venda!",
            f"Encontrado no Sympla: {nome[:120]}",
            link,
        )
        print("Encontrado:", achados)
        sinalizar_parada()
    else:
        print(f"{agora:%H:%M} — nada encontrado ainda.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Erro na checagem:", e, file=sys.stderr)
        sys.exit(1)
