import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from streamlit_drawable_canvas import st_canvas
from supabase import create_client, Client
import io
import base64
import os
import numpy as np
from PIL import Image as PILImage

st.set_page_config(
    page_title="Albaranes Atalaya",
    page_icon="☕",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Evita que la página haga scroll mientras se dibuja con el dedo
st.markdown(
    """
    <style>
    iframe[title="streamlit_drawable_canvas.st_canvas"] { touch-action: none; }
    canvas { touch-action: none; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


supabase: Client = init_supabase()


def canvas_a_b64(canvas):
    """Devuelve la firma como PNG en base64, o '' si no hay trazos."""
    if canvas is None or canvas.image_data is None:
        return ""
    arr = canvas.image_data
    if not isinstance(arr, np.ndarray) or arr.size == 0:
        return ""

    img = PILImage.fromarray(arr.astype("uint8"))
    if img.mode == "RGBA":
        fondo = PILImage.new("RGB", img.size, (255, 255, 255))
        fondo.paste(img, mask=img.split()[3])
        img = fondo
    else:
        img = img.convert("RGB")

    # Si todo es (casi) blanco, no hay firma
    if np.asarray(img).min() > 245:
        return ""

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def generar_pdf(alb, equipos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(210, 842),
        rightMargin=10, leftMargin=10, topMargin=10, bottomMargin=10,
    )
    story = []

    styles = getSampleStyleSheet()
    style_center = ParagraphStyle("Center", parent=styles["Normal"], alignment=1, fontSize=8, leading=10)
    style_bold = ParagraphStyle("Bold", parent=styles["Normal"], fontSize=7, leading=9, fontName="Helvetica-Bold")
    style_normal = ParagraphStyle("NormalTicket", parent=styles["Normal"], fontSize=7, leading=9)
    style_title = ParagraphStyle("TitleTicket", parent=styles["Normal"], alignment=1, fontSize=9, leading=11, fontName="Helvetica-Bold")

    if os.path.exists("logo.png"):
        try:
            story.append(RLImage("logo.png", width=100, height=35))
            story.append(Spacer(1, 4))
        except Exception:
            pass

    story.append(Paragraph("<b>SERVICIOS DE RECREATIVOS Y CAFÉ, S.L.</b>", style_title))
    story.append(Paragraph("<b>CAFÉS ATALAYA</b>", style_title))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>ALBARÁN #{alb['id']} - {alb['tipo_intervencion'].upper()}</b>", style_center))
    
    # Mostrar fecha adaptada a hora local de España si viene de BD
    fecha_str = alb['fecha']
    try:
        dt_utc = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
        dt_es = dt_utc.astimezone(ZoneInfo("Europe/Madrid"))
        fecha_fmt = dt_es.strftime("%Y-%m-%d %H:%M")
    except Exception:
        fecha_fmt = fecha_str[:16]

    story.append(Paragraph(f"Fecha: {fecha_fmt} | Tec: {alb['tecnico']}", style_center))
    story.append(Spacer(1, 6))

    story.append(Paragraph(f"<b>Local:</b> {alb['nombre_local']}", style_bold))
    story.append(Paragraph(f"<b>Titular:</b> {alb['titular']}", style_normal))
    story.append(Paragraph(f"<b>Dir:</b> {alb['direccion']}, {alb['localidad']}", style_normal))
    story.append(Paragraph(f"<b>Tel:</b> {alb['telefono']}", style_normal))
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>EQUIPOS AFECTADOS:</b>", style_bold))
    for e in equipos:
        story.append(Paragraph(f"• <b>{e['accion']}</b>: {e['tipo_equipo']}", style_bold))
        story.append(Paragraph(f"  {e['fabricante']} {e['modelo']}", style_normal))
        story.append(Paragraph(f"  N/S: <b>{e['num_serie']}</b>", style_normal))
        story.append(Spacer(1, 2))

    if alb.get("observaciones"):
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Obs:</b> {alb['observaciones']}", style_normal))

    story.append(Spacer(1, 6))
    story.append(Paragraph("<i>La(s) máquina(s) son propiedad de Cafés Atalaya, en régimen de cesión exclusiva.</i>", style_center))
    story.append(Spacer(1, 8))

    for titulo, campo in [
        (f"FIRMA TÉCNICO ({alb['tecnico']}):", "firma_tecnico"),
        ("FIRMA CLIENTE:", "firma_cliente"),
    ]:
        story.append(Paragraph(f"<b>{titulo}</b>", style_bold))
        if alb.get(campo):
            try:
                img_bytes = base64.b64decode(alb[campo])
                story.append(RLImage(io.BytesIO(img_bytes), width=160, height=91))
            except Exception:
                story.append(Paragraph("[Sin firma válida]", style_normal))
        else:
            story.append(Paragraph("Sin firma", style_normal))
        story.append(Spacer(1, 6))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


if os.path.exists("logo.png"):
    st.image("logo.png", width=180)
else:
    st.title("☕ Albaranes de Intervención")

st.caption("Cafés Atalaya / Servicios de Recreativos y Café, S.L.")

menu = st.radio(
    "Acción",
    ["Nuevo Albarán", "Histórico / Reimprimir"],
    horizontal=True,
    label_visibility="collapsed",
)

if menu == "Nuevo Albarán":
    st.subheader("1. Datos del Local y Cliente")
    nombre_local = st.text_input("Nombre del Local (Bar / Establecimiento)")
    col1, col2 = st.columns(2)
    with col1:
        titular = st.text_input("Titular / Empresa")
        cif = st.text_input("C.I.F. / D.N.I. Empresa")
        telefono = st.text_input("Teléfono")
    with col2:
        direccion = st.text_input("Dirección")
        localidad = st.text_input("Localidad", value="Pamplona")
        cp = st.text_input("Código Postal", value="31001")

    st.markdown("---")
    st.subheader("2. Tipo de Intervención")
    tipo_intervencion = st.selectbox(
        "Selecciona la operación principal",
        ["Instalación", "Retirada", "Sustitución"],
    )

    st.markdown("---")
    st.subheader("3. Equipos Afectados")

    if "equipos_temp" not in st.session_state:
        st.session_state.equipos_temp = []

    with st.expander("➕ Añadir una máquina a la lista", expanded=True):
        e_accion = st.selectbox("Acción sobre el equipo", ["Instalado", "Retirado"], key="eq_accion")
        e_tipo = st.selectbox("Tipo de Equipo", ["Cafetera", "Molino", "Granizadora"], key="eq_tipo")
        e_fabricante = st.text_input("Fabricante / Marca", key="eq_fab")
        e_modelo = st.text_input("Modelo", key="eq_mod")
        e_serie = st.text_input("Número de Serie (N/S)", key="eq_serie")

        if st.button("Añadir equipo al albarán"):
            if e_serie.strip():
                st.session_state.equipos_temp.append({
                    "accion": e_accion,
                    "tipo": e_tipo,
                    "fabricante": e_fabricante,
                    "modelo": e_modelo,
                    "serie": e_serie,
                })
                st.rerun()
            else:
                st.warning("Por favor, introduce el número de serie.")

    if st.session_state.equipos_temp:
        st.write("**Equipos registrados para este albarán:**")
        for idx, eq in enumerate(st.session_state.equipos_temp):
            col_info, col_del = st.columns([4, 1])
            with col_info:
                st.text(f"• [{eq['accion']}] {eq['tipo']} - {eq['fabricante']} {eq['modelo']} (N/S: {eq['serie']})")
            with col_del:
                if st.button("🗑️ Quitar", key=f"del_{idx}"):
                    st.session_state.equipos_temp.pop(idx)
                    st.rerun()

    st.markdown("---")
    st.subheader("4. Observaciones y Técnico")
    observaciones = st.text_area("Notas adicionales", placeholder="Ej: Máquina revisada, pendiente cambio de filtro...")
    nombre_tecnico = st.text_input("Nombre del Técnico", value="Mikel")

    st.markdown("---")
    st.subheader("5. Datos del Firmante y Firmas Digitales")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        nombre_firmante_cliente = st.text_input("Nombre y Cargo del Firmante", placeholder="Ej: Juan (Camarero)")
    with col_f2:
        dni_firmante_cliente = st.text_input("D.N.I. del Firmante (Opcional)", placeholder="Ej: 12345678X")

    if "reset_tec" not in st.session_state:
        st.session_state.reset_tec = 0
    if "reset_cli" not in st.session_state:
        st.session_state.reset_cli = 0

    debug = st.checkbox("🔧 Modo depuración de firmas")

    # --- Firma técnico ---
    st.text(f"Firma Técnico: {nombre_tecnico}")
    canvas_tecnico = st_canvas(
        fill_color="rgba(255, 255, 255, 1)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",
        height=160,
        width=280,
        drawing_mode="freedraw",
        return_image_data=True,
        key=f"canvas_tec_{st.session_state.reset_tec}",
    )
    if st.button("Borrar firma técnico", key="clr_tec"):
        st.session_state.reset_tec += 1
        st.rerun()

    st.markdown("")

    # --- Firma cliente ---
    st.text(f"Firma Cliente / Receptor: {nombre_firmante_cliente if nombre_firmante_cliente else 'Titular'}")
    canvas_cliente = st_canvas(
        fill_color="rgba(255, 255, 255, 1)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",
        height=160,
        width=280,
        drawing_mode="freedraw",
        return_image_data=True,
        key=f"canvas_cli_{st.session_state.reset_cli}",
    )
    if st.button("Borrar firma cliente", key="clr_cli"):
        st.session_state.reset_cli += 1
        st.rerun()

    if debug:
        st.info("Depuración de firmas:")
        for nombre, cv in [("Técnico", canvas_tecnico), ("Cliente", canvas_cliente)]:
            if cv.image_data is None:
                st.write(f"**{nombre}**: image_data = None")
            else:
                st.write(f"**{nombre}**: forma {cv.image_data.shape}, ¿firma? {bool(canvas_a_b64(cv))}")

    st.markdown("---")
    if st.button("💾 Guardar Albarán", type="primary", use_container_width=True):
        sig_tec_b64 = canvas_a_b64(canvas_tecnico)
        sig_cli_b64 = canvas_a_b64(canvas_cliente)

        if not nombre_local.strip():
            st.error("El nombre del local es obligatorio.")
        elif not st.session_state.equipos_temp:
            st.error("Debes añadir al menos un equipo a la lista.")
        elif not sig_tec_b64:
            st.error("No se ha detectado la firma del técnico.")
        elif not sig_cli_b64:
            st.error("No se ha detectado la firma del cliente.")
        else:
            # Obtener fecha y hora actual exacta en la España peninsular (Madrid)
            ahora_madrid = datetime.now(ZoneInfo("Europe/Madrid")).isoformat()

            # Construir la cadena descriptiva del titular con el firmante y el DNI si lo hay
            info_firmante = nombre_firmante_cliente if nombre_firmante_cliente else "Titular"
            if dni_firmante_cliente:
                info_firmante += f" (DNI: {dni_firmante_cliente})"

            albaran_data = {
                "fecha": ahora_madrid,
                "tipo_intervencion": tipo_intervencion,
                "nombre_local": nombre_local,
                "cif": cif,
                "direccion": direccion,
                "localidad": localidad,
                "cp": cp,
                "telefono": telefono,
                "titular": f"{titular} | Firmante: {info_firmante}",
                "observaciones": observaciones,
                "tecnico": nombre_tecnico,
                "firma_tecnico": sig_tec_b64,
                "firma_cliente": sig_cli_b64,
            }

            try:
                res = supabase.table("albaranes_instalaciones").insert(albaran_data).execute()
            except Exception as e:
                res = None
                st.error(f"Error de Supabase al guardar: {e}")

            if res is not None and res.data:
                albaran_id = res.data[0]["id"]
                for eq in st.session_state.equipos_temp:
                    supabase.table("equipos_instalados").insert({
                        "albaranes_id": albaran_id,
                        "accion": eq["accion"],
                        "tipo_equipo": eq["tipo"],
                        "fabricante": eq["fabricante"],
                        "modelo": eq["modelo"],
                        "num_serie": eq["serie"],
                    }).execute()

                st.success(f"¡Albarán #{albaran_id} guardado con éxito con sus firmas y hora peninsular!")
                st.session_state.equipos_temp = []
                st.session_state.reset_tec += 1
                st.session_state.reset_cli += 1
            elif res is not None:
                st.error("Error al guardar en la base de datos (sin datos devueltos).")

elif menu == "Histórico / Reimprimir":
    st.subheader("📁 Histórico de Intervenciones (Formato Ticket DPP-450)")
    try:
        response = (
            supabase.table("albaranes_instalaciones")
            .select("*")
            .order("id", desc=True)
            .limit(20)
            .execute()
        )
        albaranes = response.data

        if not albaranes:
            st.info("No hay albaranes registrados todavía.")
        else:
            for alb in albaranes:
                with st.expander(f"Albarán #{alb['id']} - {alb['nombre_local']} ({alb['tipo_intervencion']} - {alb['fecha'][:10]})"):
                    st.write(f"**Titular / Firmante:** {alb['titular']} | **Tel:** {alb['telefono']}")
                    st.write(f"**Dirección:** {alb['direccion']}, {alb['localidad']}")
                    st.write(f"**Técnico:** {alb['tecnico']}")

                    eq_res = supabase.table("equipos_instalados").select("*").eq("albaranes_id", alb["id"]).execute()
                    equipos = eq_res.data

                    st.write("**Equipos:**")
                    for e in equipos:
                        st.text(f"  • [{e['accion']}] {e['tipo_equipo']} - {e['fabricante']} {e['modelo']} (N/S: {e['num_serie']})")

                    if alb.get("observaciones"):
                        st.write(f"**Observaciones:** {alb['observaciones']}")

                    col_dl, col_del = st.columns(2)
                    pdf_key = f"pdf_bytes_{alb['id']}"
                    with col_dl:
                        if st.button(f"🖨️ Generar Ticket #{alb['id']}", key=f"pdf_{alb['id']}"):
                            st.session_state[pdf_key] = generar_pdf(alb, equipos)

                        if pdf_key in st.session_state:
                            st.download_button(
                                label=f"⬇️️ Descargar Ticket #{alb['id']}",
                                data=st.session_state[pdf_key],
                                file_name=f"Ticket_{alb['id']}_{alb['nombre_local'].replace(' ', '_')}.pdf",
                                mime="application/pdf",
                                key=f"dl_btn_{alb['id']}",
                            )

                    with col_del:
                        if st.button(f"🗑️ Borrar #{alb['id']}", key=f"del_db_{alb['id']}"):
                            supabase.table("equipos_instalados").delete().eq("albaranes_id", alb["id"]).execute()
                            supabase.table("albaranes_instalaciones").delete().eq("id", alb["id"]).execute()
                            st.session_state.pop(pdf_key, None)
                            st.success(f"Albarán #{alb['id']} borrado.")
                            st.rerun()

    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
