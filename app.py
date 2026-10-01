import streamlit as st
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from streamlit_drawable_canvas import st_canvas
from supabase import create_client, Client
import io
import base64
import numpy as np
from PIL import Image as PILImage

# Configuración de la página optimizada para móvil
st.set_page_config(
    page_title="Albaranes Atalaya",
    page_icon="☕",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Conexión a Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_supabase()

st.title("☕ Albaranes de Intervención")
st.caption("Cafés Atalaya / Servicios de Recreativos y Café, S.L.")

menu = st.radio("Acción", ["Nuevo Albarán", "Histórico / Reimprimir"], horizontal=True, label_visibility="collapsed")

if menu == "Nuevo Albarán":
    st.subheader("1. Datos del Local y Cliente")
    nombre_local = st.text_input("Nombre del Local (Bar / Establecimiento)")
    col1, col2 = st.columns(2)
    with col1:
        titular = st.text_input("Titular / Empresa")
        cif = st.text_input("C.I.F. / D.N.I.")
        telefono = st.text_input("Teléfono")
    with col2:
        direccion = st.text_input("Dirección")
        localidad = st.text_input("Localidad", value="Pamplona")
        cp = st.text_input("Código Postal", value="31001")

    st.markdown("---")
    st.subheader("2. Tipo de Intervención")
    tipo_intervencion = st.selectbox(
        "Selecciona la operación principal",
        ["Instalación", "Retirada", "Sustitución"]
    )

    st.markdown("---")
    st.subheader("3. Equipos Afectados")
    
    if 'equipos_temp' not in st.session_state:
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
                    "serie": e_serie
                })
                st.success("¡Equipo añadido a la lista!")
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
    st.subheader("5. Firmas Digitales")
    
    if 'reset_tec' not in st.session_state: st.session_state.reset_tec = 0
    if 'reset_cli' not in st.session_state: st.session_state.reset_cli = 0

    col_t, col_btn_t = st.columns([3, 1])
    with col_t:
        st.text(f"Firma Técnico ({nombre_tecnico})")
        canvas_tecnico = st_canvas(
            fill_color="rgba(255, 255, 255, 1)",
            stroke_width=2,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=110,
            width=200,
            drawing_mode="freedraw",
            key=f"canvas_tec_{st.session_state.reset_tec}"
        )
    with col_btn_t:
        st.write("")
        st.write("")
        if st.button("Borrar Tec.", key="clr_tec"):
            st.session_state.reset_tec += 1
            st.rerun()

    st.markdown("")
    nombre_firmante_cliente = st.text_input("Nombre y Cargo de quien firma (Ej: Juan - Camarero / Encargado)")
    
    col_c, col_btn_c = st.columns([3, 1])
    with col_c:
        st.text("Firma Cliente / Receptor")
        canvas_cliente = st_canvas(
            fill_color="rgba(255, 255, 255, 1)",
            stroke_width=2,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=110,
            width=200,
            drawing_mode="freedraw",
            key=f"canvas_cli_{st.session_state.reset_cli}"
        )
    with col_btn_c:
        st.write("")
        st.write("")
        if st.button("Borrar Cli.", key="clr_cli"):
            st.session_state.reset_cli += 1
            st.rerun()

    st.markdown("---")
    if st.button("💾 Guardar Albarán", type="primary", use_container_width=True):
        if not nombre_local.strip():
            st.error("El nombre del local es obligatorio.")
        elif not st.session_state.equipos_temp:
            st.error("Debes añadir al menos un equipo a la lista.")
        else:
            # Procesar firma técnico asegurando conversión correcta de array
            sig_tec_b64 = ""
            try:
                if canvas_tecnico.image_data is not None:
                    arr = canvas_tecnico.image_data
                    if isinstance(arr, np.ndarray) and arr.size > 0:
                        img_tec = PILImage.fromarray(arr.astype('uint8'), 'RGBA')
                        buffered_tec = io.BytesIO()
                        img_tec.save(buffered_tec, format="PNG")
                        sig_tec_b64 = base64.b64encode(buffered_tec.getvalue()).decode()
            except Exception as e:
                print(f"Error procesando firma técnico: {e}")

            # Procesar firma cliente asegurando conversión correcta de array
            sig_cli_b64 = ""
            try:
                if canvas_cliente.image_data is not None:
                    arr_c = canvas_cliente.image_data
                    if isinstance(arr_c, np.ndarray) and arr_c.size > 0:
                        img_cli = PILImage.fromarray(arr_c.astype('uint8'), 'RGBA')
                        buffered_cli = io.BytesIO()
                        img_cli.save(buffered_cli, format="PNG")
                        sig_cli_b64 = base64.b64encode(buffered_cli.getvalue()).decode()
            except Exception as e:
                print(f"Error procesando firma cliente: {e}")

            albaran_data = {
                "tipo_intervencion": tipo_intervencion,
                "nombre_local": nombre_local,
                "cif": cif,
                "direccion": direccion,
                "localidad": localidad,
                "cp": cp,
                "telefono": telefono,
                "titular": f"{titular} (Firmante: {nombre_firmante_cliente})" if nombre_firmante_cliente else titular,
                "observaciones": observaciones,
                "tecnico": nombre_tecnico,
                "firma_tecnico": sig_tec_b64,
                "firma_cliente": sig_cli_b64
            }
            
            res = supabase.table("albaranes_instalaciones").insert(albaran_data).execute()
            
            if res.data:
                albaran_id = res.data[0]["id"]
                for eq in st.session_state.equipos_temp:
                    eq_data = {
                        "albaranes_id": albaran_id,
                        "accion": eq["accion"],
                        "tipo_equipo": eq["tipo"],
                        "fabricante": eq["fabricante"],
                        "modelo": eq["modelo"],
                        "num_serie": eq["serie"]
                    }
                    supabase.table("equipos_instalados").insert(eq_data).execute()
                
                st.success(f"¡Albarán #{albaran_id} guardado con éxito en Supabase!")
                st.session_state.equipos_temp = []
            else:
                st.error("Error al guardar en la base de datos.")

elif menu == "Histórico / Reimprimir":
    st.subheader("📁 Histórico de Intervenciones y Reimpresión (Formato Ticket DPP-450)")
    try:
        response = supabase.table("albaranes_instalaciones").select("*").order("id", desc=True).limit(20).execute()
        albaranes = response.data
        
        if not albaranes:
            st.info("No hay albaranes registrados todavía.")
        else:
            for alb in albaranes:
                with st.expander(f"Albarán #{alb['id']} - {alb['nombre_local']} ({alb['tipo_intervencion']} - {alb['fecha'][:10]})"):
                    st.write(f"**Titular:** {alb['titular']} | **Tel:** {alb['telefono']}")
                    st.write(f"**Dirección:** {alb['direccion']}, {alb['localidad']}")
                    st.write(f"**Técnico:** {alb['tecnico']}")
                    
                    eq_res = supabase.table("equipos_instalados").select("*").eq("albaranes_id", alb['id']).execute()
                    equipos = eq_res.data
                    
                    st.write("**Equipos:**")
                    for e in equipos:
                        st.text(f"  • [{e['accion']}] {e['tipo_equipo']} - {e['fabricante']} {e['modelo']} (N/S: {e['num_serie']})")
                    
                    if alb['observaciones']:
                        st.write(f"**Observaciones:** {alb['observaciones']}")
                    
                    col_dl, col_del = st.columns(2)
                    with col_dl:
                        # Generador de PDF en formato TICKET (Ancho optimizado DPP-450: ~72mm / 204 puntos)
                        if st.button(f"🖨️ Generar Ticket #{alb['id']}", key=f"pdf_{alb['id']}"):
                            # Ancho de ticket térmico 80mm aprox 204 puntos, márgenes pequeños
                            buffer = io.BytesIO()
                            doc = SimpleDocTemplate(
                                buffer, 
                                pagesize=(210, 842), # Ancho exacto para impresoras térmicas portátiles tipo DPP-450
                                rightMargin=10, leftMargin=10, topMargin=10, bottomMargin=10
                            )
                            story = []
                            
                            # Estilos compactos para ticket
                            styles = getSampleStyleSheet()
                            style_center = ParagraphStyle('Center', parent=styles['Normal'], alignment=1, fontSize=8, leading=10)
                            style_bold = ParagraphStyle('Bold', parent=styles['Normal'], fontSize=7, leading=9, fontName='Helvetica-Bold')
                            style_normal = ParagraphStyle('NormalTicket', parent=styles['Normal'], fontSize=7, leading=9)
                            style_title = ParagraphStyle('TitleTicket', parent=styles['Normal'], alignment=1, fontSize=9, leading=11, fontName='Helvetica-Bold')
                            
                            story.append(Paragraph("<b>SERVICIOS DE RECREATIVOS Y CAFÉ, S.L.</b>", style_title))
                            story.append(Paragraph("<b>CAFÉS ATALAYA</b>", style_title))
                            story.append(Spacer(1, 4))
                            story.append(Paragraph(f"<b>ALBARÁN #{alb['id']} - {alb['tipo_intervencion'].upper()}</b>", style_center))
                            story.append(Paragraph(f"Fecha: {alb['fecha'][:16]} | Tec: {alb['tecnico']}", style_center))
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
                                
                            if alb['observaciones']:
                                story.append(Spacer(1, 4))
                                story.append(Paragraph(f"<b>Obs:</b> {alb['observaciones']}", style_normal))
                                
                            story.append(Spacer(1, 6))
                            story.append(Paragraph("<i>La(s) máquina(s) son propiedad de Cafés Atalaya, en régimen de cesión exclusiva.</i>", style_center))
                            story.append(Spacer(1, 8))
                            
                            # Firmas adaptadas a ancho de ticket térmico
                            story.append(Paragraph("<b>FIRMA TÉCNICO:</b>", style_bold))
                            if alb['firma_tecnico']:
                                try:
                                    img_t_bytes = base64.b64decode(alb['firma_tecnico'])
                                    story.append(RLImage(io.BytesIO(img_t_bytes), width=160, height=60))
                                except Exception:
                                    story.append(Paragraph("[Error cargando firma]", style_normal))
                            else:
                                story.append(Paragraph("Sin firma", style_normal))
                                
                            story.append(Spacer(1, 6))
                            story.append(Paragraph("<b>FIRMA CLIENTE:</b>", style_bold))
                            if alb['firma_cliente']:
                                try:
                                    img_c_bytes = base64.b64decode(alb['firma_cliente'])
                                    story.append(RLImage(io.BytesIO(img_c_bytes), width=160, height=60))
                                except Exception:
                                    story.append(Paragraph("[Error cargando firma]", style_normal))
                            else:
                                story.append(Paragraph("Sin firma", style_normal))
                                
                            doc.build(story)
                            buffer.seek(0)
                            
                            st.download_button(
                                label=f"🖨️ Descargar Ticket Térmico #{alb['id']}",
                                data=buffer,
                                file_name=f"Ticket_{alb['id']}_{alb['nombre_local'].replace(' ', '_')}.pdf",
                                mime="application/pdf",
                                key=f"dl_btn_{alb['id']}"
                            )

                    with col_del:
                        if st.button(f"🗑️ Borrar #{alb['id']}", key=f"del_db_{alb['id']}"):
                            supabase.table("equipos_instalados").delete().eq("albaranes_id", alb['id']).execute()
                            supabase.table("albaranes_instalaciones").delete().eq("id", alb['id']).execute()
                            st.success(f"Albarán #{alb['id']} borrado.")
                            st.rerun()

    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
