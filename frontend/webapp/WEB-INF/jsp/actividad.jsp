<%--
  Ver actividad (CC-09 y CC-22): historial de eventos del simulador en vivo.
  La JSP solo pinta la estructura; js/actividad.js pide los datos a /api/actividad
  (ApiLecturaServlet, CC-21), recibe los nuevos por Server-Sent Events (js/vivo.js)
  y los inserta con textContent.
--%>
<%@ page contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" %>
<%@ include file="/WEB-INF/jsp/fragmentos/cabecera.jspf" %>

<nav class="ruta-migas" aria-label="Ruta">
    <a href="${pageContext.request.contextPath}/resumen">Resumen ejecutivo</a> / Actividad en vivo
</nav>
<header class="vista-encabezado">
    <div>
        <h1 class="titulo-vista">Actividad en vivo</h1>
        <p class="vista-sub" id="actividad-estado">Cargando…</p>
    </div>
    <div class="vista-frescura">
        <span class="etiqueta-origen">Datos simulados</span>
    </div>
</header>

<p class="aviso aviso-error" id="actividad-error" role="alert" hidden></p>

<section class="tarjeta" aria-labelledby="titulo-actividad">
    <div class="tarjeta-encabezado">
        <div>
            <h2 id="titulo-actividad" class="tarjeta-titulo">Eventos del simulador</h2>
            <p class="tarjeta-sub">Del más reciente al más antiguo · fecha y hora simuladas · los nuevos aparecen arriba</p>
        </div>
    </div>
    <ol class="actividad" id="actividad-lista"></ol>
    <p class="texto-suave" id="actividad-vacio" hidden>Todavía no hay actividad: el simulador no se ha iniciado.</p>
    <button type="button" class="boton boton-claro" id="actividad-mas" hidden>Cargar eventos anteriores</button>
</section>

<script src="${pageContext.request.contextPath}/js/comun.js?v=${sc:esc(version)}"></script>
<script src="${pageContext.request.contextPath}/js/vivo.js?v=${sc:esc(version)}"></script>
<script src="${pageContext.request.contextPath}/js/actividad.js?v=${sc:esc(version)}"></script>

<%@ include file="/WEB-INF/jsp/fragmentos/pie.jspf" %>