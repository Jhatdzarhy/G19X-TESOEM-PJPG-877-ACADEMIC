<%--
  Vista de un modulo del PDR (seccion 6; diseno CC-10 y CC-24): indicadores del modulo,
  grafica principal, tabla de detalle y casos abiertos del Centro de soluciones.
  La JSP solo pinta la estructura; js/modulo.js pide los datos a /api/ (Servlets, CC-21)
  y los inserta con textContent. El modulo lo indica data-modulo (PaginaServlet).
--%>
<%@ page contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" %>
<%@ include file="/WEB-INF/jsp/fragmentos/cabecera.jspf" %>

<div id="modulo" data-modulo="${sc:esc(vista)}">
    <header class="vista-encabezado">
        <div>
            <h1 class="titulo-vista">${sc:esc(titulo)}</h1>
            <p class="vista-sub" id="modulo-sub">Cargando…</p>
        </div>
        <div class="vista-frescura">
            <span class="etiqueta-origen" id="modulo-origen">Datos simulados</span>
            <span id="modulo-actualizado" class="texto-suave"></span>
        </div>
    </header>

    <p class="aviso aviso-error" id="modulo-error" role="alert" hidden></p>

    <section class="kpis-modulo" id="modulo-kpis" aria-label="Indicadores del módulo"></section>

    <section class="tarjeta" id="modulo-grafica-caja" aria-labelledby="modulo-grafica-titulo" hidden>
        <div class="tarjeta-encabezado">
            <div>
                <h2 id="modulo-grafica-titulo" class="tarjeta-titulo"></h2>
                <p class="tarjeta-sub" id="modulo-grafica-sub"></p>
            </div>
        </div>
        <div class="grafica-modulo" id="modulo-grafica-envoltura">
            <canvas id="modulo-grafica" role="img"></canvas>
        </div>
        <p class="nota-grafica" id="modulo-grafica-nota"></p>
    </section>

    <section class="tarjeta" aria-labelledby="modulo-tabla-titulo">
        <div class="tarjeta-encabezado">
            <div>
                <h2 id="modulo-tabla-titulo" class="tarjeta-titulo"></h2>
                <p class="tarjeta-sub" id="modulo-tabla-sub"></p>
            </div>
        </div>
        <div class="tabla-desplazable">
            <table class="tabla-modulo" id="modulo-tabla">
                <thead></thead>
                <tbody></tbody>
            </table>
        </div>
        <p class="texto-suave" id="modulo-tabla-vacio" hidden></p>
    </section>

    <section class="tarjeta" id="modulo-casos-caja" aria-labelledby="modulo-casos-titulo" hidden>
        <div class="tarjeta-encabezado">
            <div>
                <h2 id="modulo-casos-titulo" class="tarjeta-titulo">Casos abiertos del Centro de soluciones</h2>
                <p class="tarjeta-sub">Recomendaciones de la IA para este módulo, por impacto en MXN · la decisión es humana</p>
            </div>
        </div>
        <ul class="casos-modulo" id="modulo-casos"></ul>
        <p class="texto-suave" id="modulo-casos-vacio" hidden>No hay casos abiertos en este módulo.</p>
    </section>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js"
        integrity="sha256-SERKgtTty1vsDxll+qzd4Y2cF9swY9BCq62i9wXJ9Uo=" crossorigin="anonymous"></script>
<script src="${pageContext.request.contextPath}/js/comun.js?v=${sc:esc(version)}"></script>
<script src="${pageContext.request.contextPath}/js/modulo.js?v=${sc:esc(version)}"></script>

<%@ include file="/WEB-INF/jsp/fragmentos/pie.jspf" %>