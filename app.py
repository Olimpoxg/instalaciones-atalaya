import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
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

# ==========================================
# SISTEMA DE AUTENTICACIÓN POR CONTRASEÑA
# ==========================================
def verificar_password():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if st.session_state.autenticado:
        return True

    if "APP_PASSWORD" not in st.secrets:
        st.error("⚠️️ Falta configurar 'APP_PASSWORD' en los Secrets de Streamlit Cloud.")
        return False

    if os.path.exists("logo.png"):
        try:
            st.image("logo.png", width=180)
        except Exception:
            pass
            
    st.title("☕ Acceso Restringido")
    st.subheader("Cafés Atalaya / Control de Intervenciones")
    
    password_ingresada = st.text_input("Introduce la contraseña de acceso", type="password")
    
    if st.button("Entrar", type="primary"):
        if password_ingresada == st.secrets["APP_PASSWORD"]:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    return False

if not verificar_password():
    st.stop()
# ==========================================

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

    if np.asarray(img).min() > 245:
        return ""

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ----------------------------------------------------
# 1. GENERADOR DE PDF TÉRMICO (Ancho DPP-450)
# ----------------------------------------------------
def generar_pdf_termico(alb, equipos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(210, 842),
        rightMargin=10, leftMargin=10, topMargin=10, bottomMargin=10,
    )
    story = []

    styles = getSampleStyleSheet()
    style_center = ParagraphStyle("Center", parent=styles["Normal"], alignment=1, fontSize=9, leading=12)
    style_bold = ParagraphStyle("Bold", parent=styles["Normal"], fontSize=9, leading=13, fontName="Helvetica-Bold")
    style_normal = ParagraphStyle("NormalTicket", parent=styles["Normal"], fontSize=9, leading=13)
    style_title = ParagraphStyle("TitleTicket", parent=styles["Normal"], alignment=1, fontSize=10, leading=13, fontName="Helvetica-Bold")
    style_header_tipo = ParagraphStyle("HeaderTipo", parent=styles["Normal"], alignment=1, fontSize=12, leading=15, fontName="Helvetica-Bold")

    if os.path.exists("logo.png"):
        try:
            story.append(RLImage("logo.png", width=120, height=42))
            story.append(Spacer(1, 6))
        except Exception:
            pass

    story.append(Paragraph("<b>SERVICIOS DE RECREATIVOS Y CAFÉ, S.L.</b>", style_title))
    story.append(Paragraph("<b>CAFÉS ATALAYA</b>", style_title))
    story.append(Spacer(1, 6))
    
    story.append(Paragraph(f"<b>{alb['tipo_intervencion'].upper()}</b>", style_header_tipo))
    story.append(Spacer(1, 4))
    
    fecha_str = alb['fecha']
    try:
        dt_utc = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
        dt_es = dt_utc.astimezone(ZoneInfo("Europe/Madrid"))
        fecha_fmt = dt_es.strftime("%d/%m/%Y %H:%M")
    except Exception:
        fecha_fmt = fecha_str[:16]

    story.append(Paragraph(f"<b>Fecha:</b> {fecha_fmt}", style_center))
    story.append(Spacer(1, 8))

    story.append(Paragraph(f"<b>Local:</b> {alb['nombre_local']}", style_bold))
    story.append(Paragraph(f"<b>Titular:</b> {alb['titular']}", style_normal))
    story.append(Paragraph(f"<b>Dir:</b> {alb['direccion']}, {alb['localidad']}", style_normal))
    story.append(Paragraph(f"<b>Tel:</b> {alb['telefono']}", style_normal))
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>EQUIPOS AFECTADOS:</b>", style_bold))
    for e in equipos:
        story.append(Paragraph(f"• <b>{e['accion']}</b>: {e['tipo_equipo']}", style_bold))
        story.append(Paragraph(f"  {e['fabricante']} {e['modelo']}", style_normal))
        story.append(Paragraph(f"  N/S: <b>{e['num_serie']}</b>", style_normal))
        story.append(Spacer(1, 5))

    if alb.get("observaciones"):
        story.append(Spacer(1, 4))
        story.append(Paragraph("<b>OBSERVACIONES:</b>", style_bold))
        story.append(Paragraph(f"{alb['observaciones']}", style_normal))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<i>La(s) máquina(s) son propiedad de Cafés Atalaya, en régimen de cesión exclusiva.</i>", style_center))
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"<b>FIRMA TÉCNICO ({alb['tecnico']}):</b>", style_bold))
    if alb.get("firma_tecnico"):
        try:
            img_bytes = base64.b64decode(alb["firma_tecnico"])
            story.append(RLImage(io.BytesIO(img_bytes), width=170, height=95))
        except Exception:
            story.append(Paragraph("[Sin firma válida]", style_normal))
    else:
        story.append(Paragraph("Sin firma", style_normal))
    story.append(Spacer(1, 10))

    nombre_f = alb.get('firmante_nombre', 'Titular')
    dni_f = alb.get('firmante_dni', '')
    label_cliente = f"FIRMA CLIENTE ({nombre_f}"
    if dni_f:
        label_cliente += f" - DNI: {dni_f}"
    label_cliente += "):"

    story.append(Paragraph(f"<b>{label_cliente}</b>", style_bold))
    if alb.get("firma_cliente"):
        try:
            img_bytes = base64.b64decode(alb["firma_cliente"])
            story.append(RLImage(io.BytesIO(img_bytes), width=170, height=95))
        except Exception:
            story.append(Paragraph("[Sin firma válida]", style_normal))
    else:
        story.append(Paragraph("Sin firma", style_normal))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ----------------------------------------------------
# 2. GENERADOR DE PDF OFICIAL EN FORMATO A4 (Oficina / Mail)
# ----------------------------------------------------
def generar_pdf_a4(alb, equipos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40,
    )
    story = []

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle("A4Title", parent=styles["Normal"], alignment=1, fontSize=15, leading=18, fontName="Helvetica-Bold")
    style_subtitle = ParagraphStyle("A4Sub", parent=styles["Normal"], alignment=1, fontSize=10, leading=14, fontName="Helvetica-Bold")
    style_normal = ParagraphStyle("A4Normal", parent=styles["Normal"], fontSize=9, leading=13)
    style_bold = ParagraphStyle("A4Bold", parent=styles["Normal"], fontSize=9, leading=13, fontName="Helvetica-Bold")

    if os.path.exists("logo.png"):
        try:
            story.append(RLImage("logo.png", width=130, height=45))
            story.append(Spacer(1, 8))
        except Exception:
            pass

    story.append(Paragraph("<b>SERVICIOS DE RECREATIVOS Y CAFÉ, S.L. / CAFÉS ATALAYA</b>", style_subtitle))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>ALBARÁN DE INTERVENCIÓN — {alb['tipo_intervencion'].upper()}</b>", style_title))
    story.append(Spacer(1, 12))

    fecha_str = alb['fecha']
    try:
        dt_utc = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
        dt_es = dt_utc.astimezone(ZoneInfo("Europe/Madrid"))
        fecha_fmt = dt_es.strftime("%d/%m/%Y %H:%M")
    except Exception:
        fecha_fmt = fecha_str[:16]

    data_cabecera = [
        [Paragraph(f"<b>Local:</b> {alb['nombre_local']}", style_normal), Paragraph(f"<b>Fecha:</b> {fecha_fmt}", style_normal)],
        [Paragraph(f"<b>Titular:</b> {alb['titular']}", style_normal), Paragraph(f"<b>Técnico:</b> {alb['tecnico']}", style_normal)],
        [Paragraph(f"<b>Dirección:</b> {alb['direccion']}, {alb['localidad']} ({alb['cp']})", style_normal), Paragraph(f"<b>Teléfono:</b> {alb['telefono']}", style_normal)]
    ]
    t_cabecera = Table(data_cabecera, colWidths=[270, 260])
    t_cabecera.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_cabecera)
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>EQUIPOS AFECTADOS</b>", style_bold))
    story.append(Spacer(1, 4))
    
    data_equipos = [["Acción", "Tipo", "Fabricante", "Modelo", "N/S"]]
    for e in equipos:
        data_equipos.append([e['accion'], e['tipo_equipo'], e['fabricante'] or '', e['modelo'] or '', e['num_serie'] or ''])
    
    t_eq = Table(data_equipos, colWidths=[70, 80, 115, 115, 150])
    t_eq.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    story.append(t_eq)
    story.append(Spacer(1, 10))

    if alb.get("observaciones"):
        story.append(Paragraph("<b>OBSERVACIONES:</b>", style_bold))
        story.append(Paragraph(alb['observaciones'], style_normal))
        story.append(Spacer(1, 10))

    story.append(Paragraph("<i>La(s) máquina(s) detallada(s) son propiedad de Servicios de Recreativos y Café, S.L. / Cafés Atalaya, quedando depositadas en calidad de cesión para su explotación exclusiva en el establecimiento indicado.</i>", style_normal))
    story.append(Spacer(1, 15))

    img_tec_flow = Paragraph("Sin firma", style_normal)
    img_cli_flow = Paragraph("Sin firma", style_normal)

    if alb.get("firma_tecnico"):
        try:
            img_t_bytes = base64.b64decode(alb["firma_tecnico"])
            img_tec_flow = RLImage(io.BytesIO(img_t_bytes), width=160, height=75)
        except Exception: pass

    if alb.get("firma_cliente"):
        try:
            img_c_bytes = base64.b64decode(alb["firma_cliente"])
            img_cli_flow = RLImage(io.BytesIO(img_c_bytes), width=160, height=75)
        except Exception: pass

    nombre_f = alb.get('firmante_nombre', 'Titular')
    dni_f = alb.get('firmante_dni', '')
    txt_cliente = f"Firma Cliente ({nombre_f}"
    if dni_f:
        txt_cliente += f" - DNI: {dni_f}"
    txt_cliente += ")"

    sig_data = [
        [Paragraph(f"<b>Firma Técnico ({alb['tecnico']})</b>", style_bold), Paragraph(f"<b>{txt_cliente}</b>", style_bold)],
        [img_tec_flow, img_cli_flow]
    ]
    t_sig = Table(sig_data, colWidths=[265, 265])
    t_sig.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_sig)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ----------------------------------------------------
# INTERFAZ DE USUARIO
# ----------------------------------------------------
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
    st.subheader("2. Equipos Afectados")
    st.info("Añade las máquinas que intervienen. El tipo de albarán se calculará solo.")

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
    st.subheader("3. Observaciones y Técnico")
    observaciones = st.text_area("Notas adicionales", placeholder="Ej: Máquina revisada, pendiente cambio de filtro...")
    nombre_tecnico = st.text_input("Nombre del Técnico", value="Mikel")

    st.markdown("---")
    st.subheader("4. Datos del Firmante y Firmas Digitales")
    
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
            acciones = [eq["accion"] for eq in st.session_state.equipos_temp]
            tiene_instalado = "Instalado" in acciones
            tiene_retirado = "Retirado" in acciones

            if tiene_instalado and tiene_retirado:
                tipo_intervencion = "Sustitución"
            elif tiene_instalado:
                tipo_intervencion = "Instalación"
            else:
                tipo_intervencion = "Retirada"

            ahora_madrid = datetime.now(ZoneInfo("Europe/Madrid")).isoformat()

            albaran_data = {
                "fecha": ahora_madrid,
                "tipo_intervencion": tipo_intervencion,
                "nombre_local": nombre_local,
                "cif": cif,
                "direccion": direccion,
                "localidad": localidad,
                "cp": cp,
                "telefono": telefono,
                "titular": titular,
                "firmante_nombre": nombre_firmante_cliente if nombre_firmante_cliente else "Titular",
                "firmante_dni": dni_firmante_cliente,
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

                st.success(f"¡Albarán guardado como '{tipo_intervencion}' con éxito!")
                st.session_state.equipos_temp = []
                st.session_state.reset_tec += 1
                st.session_state.reset_cli += 1
            elif res is not None:
                st.error("Error al guardar en la base de datos (sin datos devueltos).")

elif menu == "Histórico / Reimprimir":
    st.subheader("📁 Histórico y Generación de Documentos")
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
                firmante_txt = alb.get('firmante_nombre', 'Titular')
                if alb.get('firmante_dni'):
                    firmante_txt += f" (DNI: {alb['firmante_dni']})"

                with st.expander(f"{alb['tipo_intervencion'].upper()} - {alb['nombre_local']} ({alb['fecha'][:10]})"):
                    st.write(f"**Titular:** {alb['titular']} | **Firmante:** {firmante_txt}")
                    st.write(f"**Tel:** {alb['telefono']} | **Dir:** {alb['direccion']}, {alb['localidad']}")
                    st.write(f"**Técnico:** {alb['tecnico']}")

                    eq_res = supabase.table("equipos_instalados").select("*").eq("albaranes_id", alb["id"]).execute()
                    equipos = eq_res.data

                    st.write("**Equipos:**")
                    for e in equipos:
                        st.text(f"  • [{e['accion']}] {e['tipo_equipo']} - {e['fabricante']} {e['modelo']} (N/S: {e['num_serie']})")

                    if alb.get("observaciones"):
                        st.write(f"**Observaciones:** {alb['observaciones']}")

                    st.markdown("---")
                    
                    col_term, col_a4, col_del = st.columns(3)
                    
                    pdf_termico_key = f"termico_{alb['id']}"
                    pdf_a4_key = f"a4_{alb['id']}"

                    with col_term:
                        if st.button(f"🖨️ Ticket Térmico", key=f"btn_t_{alb['id']}"):
                            st.session_state[pdf_termico_key] = generar_pdf_termico(alb, equipos)
                        if pdf_termico_key in st.session_state:
                            st.download_button(
                                label=f"⬇ Descargar Térmico",
                                data=st.session_state[pdf_termico_key],
                                file_name=f"Ticket_{alb['tipo_intervencion']}_{alb['nombre_local'].replace(' ', '_')}.pdf",
                                mime="application/pdf",
                                key=f"dl_t_{alb['id']}",
                            )

                    with col_a4:
                        if st.button(f"📄 PDF Oficial A4", key=f"btn_a_{alb['id']}"):
                            st.session_state[pdf_a4_key] = generar_pdf_a4(alb, equipos)
                        if pdf_a4_key in st.session_state:
                            st.download_button(
                                label=f"⬇ Descargar A4 / Mail",
                                data=st.session_state[pdf_a4_key],
                                file_name=f"Albaran_{alb['tipo_intervencion']}_{alb['nombre_local'].replace(' ', '_')}.pdf",
                                mime="application/pdf",
                                key=f"dl_a_{alb['id']}",
                            )

                    with col_del:
                        st.write("")
                        if st.button(f"🗑️ Borrar", key=f"del_db_{alb['id']}"):
                            supabase.table("equipos_instalados").delete().eq("albaranes_id", alb["id"]).execute()
                            supabase.table("albaranes_instalaciones").delete().eq("id", alb["id"]).execute()
                            st.session_state.pop(pdf_termico_key, None)
                            st.session_state.pop(pdf_a4_key, None)
                            st.success("Borrado.")
                            st.rerun()

    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
