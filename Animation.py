import asyncio
import math
import flet as ft
import flet.canvas as cv

CYAN, MAGENTA, VIOLET, BLUE = "#00F0FF", "#FF2BD6", "#7B61FF", "#2D9CFF"
STAGE = 540
TAU = 2 * math.pi


def hud_ring(size, color, width, arcs, glow=True, pad=10):
    """Anillo dibujado con arcos (segmentos) + un punto luminoso orbitando."""
    inner = size - pad * 2
    shapes = []
    for start, sweep in arcs:
        if glow:  # falso resplandor: trazo ancho y tenue debajo
            shapes.append(ft.canvas.Arc(
                x=pad, y=pad, width=inner, height=inner,
                start_angle=math.radians(start), sweep_angle=math.radians(sweep),
                use_center=False,
                paint=ft.Paint(color=ft.Colors.with_opacity(0.18, color),
                               stroke_width=width * 4, style=ft.PaintingStyle.STROKE,
                               stroke_cap=ft.StrokeCap.ROUND),
            ))
        shapes.append(ft.canvas.Arc(
            x=pad, y=pad, width=inner, height=inner,
            start_angle=math.radians(start), sweep_angle=math.radians(sweep),
            use_center=False,
            paint=ft.Paint(color=color, stroke_width=width,
                           style=ft.PaintingStyle.STROKE,
                           stroke_cap=ft.StrokeCap.ROUND),
        ))

    dot = ft.Container(
        width=10, height=10, left=size / 2 - 5, top=pad - 5,
        shape=ft.BoxShape.CIRCLE, bgcolor="white",
        shadow=ft.BoxShadow(blur_radius=18, spread_radius=3, color=color),
    )
    return ft.Container(
        width=size, height=size, left=(STAGE - size) / 2, top=(STAGE - size) / 2,
        content=ft.Stack([ft.canvas.Canvas(shapes=shapes, width=size, height=size), dot],
                         width=size, height=size),
        rotate=0,
    )


def tick_ring(size, color, pad=10):
    """Anillo de marcas finas tipo reloj/radar."""
    inner = size - pad * 2
    shapes = [
        ft.canvas.Arc(
            x=pad, y=pad, width=inner, height=inner,
            start_angle=math.radians(i * 5), sweep_angle=math.radians(1.2),
            use_center=False,
            paint=ft.Paint(color=ft.Colors.with_opacity(0.55, color), stroke_width=6,
                           style=ft.PaintingStyle.STROKE),
        )
        for i in range(72)
    ]
    return ft.Container(
        width=size, height=size, left=(STAGE - size) / 2, top=(STAGE - size) / 2,
        content=ft.canvas.Canvas(shapes=shapes, width=size, height=size),
        rotate=0,
    )


async def main(page: ft.Page):
    page.title = "AERO CORE"
    page.padding = 0
    page.bgcolor = "#05060F"
    page.theme_mode = ft.ThemeMode.DARK

    T = 8  # segundos por ciclo de animación (más alto = más lento)
    linear = ft.Animation(T * 1000, ft.AnimationCurve.LINEAR)

    # ── Anillos: (control, vueltas por ciclo; negativo = sentido contrario)
    ticks = tick_ring(520, BLUE)
    r1 = hud_ring(470, CYAN, 3, [(0, 80), (120, 60), (230, 100)])
    r2 = hud_ring(390, MAGENTA, 3, [(20, 110), (170, 40), (250, 70)])
    r3 = hud_ring(310, VIOLET, 4, [(0, 150), (180, 120)])
    r4 = hud_ring(230, CYAN, 2, [(40, 60), (160, 60), (280, 60)], glow=False)
    rings = [(ticks, -1), (r1, 1), (r2, -2), (r3, 3), (r4, -4)]
    for ring, _ in rings:
        ring.animate_rotation = linear

    # ── Núcleo pulsante
    halo = ft.Container(
        width=190, height=190, left=(STAGE - 190) / 2, top=(STAGE - 190) / 2,
        shape=ft.BoxShape.CIRCLE,
        gradient=ft.RadialGradient(colors=[
            ft.Colors.with_opacity(0.35, CYAN), ft.Colors.with_opacity(0.0, CYAN)]),
        scale=1, animate_scale=ft.Animation(1600, ft.AnimationCurve.EASE_IN_OUT),
    )
    core = ft.Container(
        width=100, height=100, left=(STAGE - 100) / 2, top=(STAGE - 100) / 2,
        shape=ft.BoxShape.CIRCLE,
        gradient=ft.RadialGradient(colors=["#FFFFFF", CYAN, VIOLET]),
        shadow=ft.BoxShadow(blur_radius=60, spread_radius=8,
                            color=ft.Colors.with_opacity(0.7, CYAN)),
        scale=1, animate_scale=ft.Animation(1600, ft.AnimationCurve.EASE_IN_OUT),
    )

    # ── Texto de estado
    status = ft.Text("INICIALIZANDO", size=15, color=CYAN, weight=ft.FontWeight.W_600,
                     style=ft.TextStyle(letter_spacing=6),
                     opacity=1, animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT))
    title = ft.Text("A E R O   C O R E", size=26, weight=ft.FontWeight.W_300, color="white")

    stage = ft.Stack([ticks, r1, r2, r3, r4, halo, core], width=STAGE, height=STAGE)

    page.add(
        ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                colors=["#05060F", "#0A0F2C", "#150A2E"]),
            content=ft.Column(
                [stage, title, status],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=14,
            ),
        )
    )

    # ── Bucles de animación
    async def spin():
        angle = 0.0
        while True:
            angle += TAU
            for ring, turns in rings:
                ring.rotate = angle * turns
            page.update()
            await asyncio.sleep(T)

    async def pulse():
        big = True
        while True:
            s = 1.18 if big else 0.92
            core.scale = s
            halo.scale = 1.25 if big else 0.9
            page.update()
            big = not big
            await asyncio.sleep(1.6)

    async def texts():
        msgs = ["INICIALIZANDO", "SINCRONIZANDO NÚCLEO", "ANALIZANDO DATOS",
                "SISTEMA EN LÍNEA"]
        i = 0
        while True:
            await asyncio.sleep(2.5)
            status.opacity = 0
            page.update()
            await asyncio.sleep(0.5)
            i = (i + 1) % len(msgs)
            status.value = msgs[i]
            status.opacity = 1
            page.update()

    await asyncio.gather(spin(), pulse(), texts())


ft.run(main)