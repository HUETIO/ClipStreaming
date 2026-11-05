import asyncio
import random
import flet as ft
import flet.canvas as cv

CYAN, MAGENTA, VIOLET, BLUE = "#00F0FF", "#FF2BD6", "#7B61FF", "#2D9CFF"
GLYPHS = "01ABCDEF<>/{}[]#$%&*+=ΣΩΔλπ∞"


def animated_background(page: ft.Page, content: ft.Control) -> ft.Stack:
    """Devuelve un Stack con el fondo animado y `content` encima."""
    W = int(page.width or 1280)
    H = int(page.height or 800)
    W, H = max(W, 1280), max(H, 800)  # margen para cuando se maximiza la ventana

    # ── 1. Gradiente base
    base = ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
            colors=["#04050E", "#0A0F2C", "#150A2E"]),
    )

    # ── 2. Rejilla tenue
    grid_paint = ft.Paint(color=ft.Colors.with_opacity(0.07, CYAN), stroke_width=1)
    shapes = [cv.Line(x, 0, x, H, paint=grid_paint) for x in range(0, W, 48)]
    shapes += [cv.Line(0, y, W, y, paint=grid_paint) for y in range(0, H, 48)]
    grid = ft.Container(content=cv.Canvas(shapes=shapes, width=W, height=H),
                        left=0, top=0)

    # ── 3. Auroras (círculos con degradado radial que se desvanece)
    blob_anim = ft.Animation(9000, ft.AnimationCurve.EASE_IN_OUT)
    blobs = []
    for color, size in [(CYAN, 520), (MAGENTA, 460), (VIOLET, 600), (BLUE, 420)]:
        blobs.append(ft.Container(
            width=size, height=size, shape=ft.BoxShape.CIRCLE,
            left=random.randint(0, W - size // 2), top=random.randint(0, H - size // 2),
            gradient=ft.RadialGradient(colors=[
                ft.Colors.with_opacity(0.38, color), ft.Colors.with_opacity(0.0, color)]),
            animate_position=blob_anim,
        ))

    # ── 4. Línea de escaneo
    scan = ft.Container(
        height=2, left=0, top=-10, width=W,
        gradient=ft.LinearGradient(colors=[
            ft.Colors.with_opacity(0.0, CYAN), ft.Colors.with_opacity(0.5, CYAN),
            ft.Colors.with_opacity(0.0, CYAN)]),
        animate_position=ft.Animation(6000, ft.AnimationCurve.LINEAR),
    )

    # ── 5. Letras flotantes
    glyph_anim = ft.Animation(5000, ft.AnimationCurve.EASE_IN_OUT)
    glyphs = [
        ft.Text(random.choice(GLYPHS), size=random.choice([14, 18, 24]),
                color=random.choice([CYAN, MAGENTA, VIOLET]),
                font_family="Consolas", opacity=0, left=0, top=0,
                animate_position=glyph_anim,
                animate_opacity=ft.Animation(1200, ft.AnimationCurve.EASE_IN_OUT))
        for _ in range(38)
    ]

    # ── Bucles de animación
    async def drift_blobs():
        while True:
            for b in blobs:
                b.left = random.randint(-150, W - 250)
                b.top = random.randint(-150, H - 250)
            page.update()
            await asyncio.sleep(9)

    async def scanner():
        while True:
            scan.top = H
            page.update()
            await asyncio.sleep(6)
            # reinicio instantáneo arriba, sin animar
            scan.animate_position = None
            scan.top = -10
            page.update()
            await asyncio.sleep(0.05)
            scan.animate_position = ft.Animation(6000, ft.AnimationCurve.LINEAR)

    async def float_glyph(g: ft.Text):
        await asyncio.sleep(random.uniform(0, 5))
        while True:
            g.animate_position = None          # salto instantáneo
            g.value = random.choice(GLYPHS)
            g.left, g.top = random.randint(0, W - 30), random.randint(H // 3, H)
            g.opacity = 0
            page.update()
            await asyncio.sleep(0.05)
            g.animate_position = glyph_anim    # ahora sí, deriva hacia arriba
            g.opacity = random.uniform(0.25, 0.7)
            g.top -= random.randint(120, 260)
            page.update()
            await asyncio.sleep(3.8)
            g.opacity = 0
            page.update()
            await asyncio.sleep(1.4)

    page.run_task(drift_blobs)
    page.run_task(scanner)
    for g in glyphs:
        page.run_task(float_glyph, g)

    return ft.Stack(
        [base, grid, *blobs, scan, *glyphs,
         ft.Container(content=content, expand=True, alignment=ft.Alignment(0, 0))],
        expand=True,
    )


def main(page: ft.Page):
    page.title = "Fondo animado"
    page.padding = 0
    page.bgcolor = "#04050E"
    page.theme_mode = ft.ThemeMode.DARK

    # Tarjeta de ejemplo (estilo cristal) para ver el fondo detrás
    card = ft.Container(
        width=380, padding=32, border_radius=24,
        bgcolor=ft.Colors.with_opacity(0.10, "#FFFFFF"),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, CYAN)),
        shadow=ft.BoxShadow(blur_radius=50, color=ft.Colors.with_opacity(0.25, CYAN)),
        content=ft.Column(
            [
                ft.Text("AERO CORE", size=28, weight=ft.FontWeight.W_300, color="white"),
                ft.Text("Tu contenido va aquí", color=ft.Colors.with_opacity(0.7, "white")),
                ft.FilledButton("Comenzar"),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=16,
        ),
    )

    page.add(animated_background(page, card))


ft.run(main)