<%--
  Resumen ejecutivo (diseno CC-10): Estado de la cadena, Que atender hoy y
  Demanda y pronostico. La JSP solo pinta la estructura; js/resumen.js pide los
  datos a /api/ (ApiLecturaServlet, CC-21) y los inserta con textContent.
--%>
<%@ page contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" %>
<%@ include file="/WEB-INF/jsp/fragmentos/cabecera.jspf" %>

<header class="vista-encabezado">
    <div>
        <h1 class="titulo-vista">Resumen ejecutivo</h1>
        <p class="vista-sub" id="resumen-periodo">Cargando datos…</p>
    </div>
    <div class="vista-frescura">
        <span class="etiqueta-origen">Datos simulados</span>
        <span id="resumen-actualizado" class="texto-suave"></span>
    </div>
</header>

<section class="franja-vivo" id="franja-vivo" data-estado="RECONECTANDO" aria-label="Actividad en vivo">
    <span class="franja-estado"><span class="franja-punto" aria-hidden="true"></span><span id="franja-estado">Conectando</span></span>
    <time class="franja-hora" id="franja-hora"></time>
    <span class="franja-titulo" id="franja-titulo"></span>
    <span id="franja-insignia"></span>
    <a class="franja-enlace" id="franja-contador" href="${pageContext.request.contextPath}/actividad">Ver actividad</a>
</section>

<p class="aviso aviso-error" id="resumen-error" role="alert" hidden></p>

<section class="tarjeta" aria-labelledby="titulo-estado">
    <div class="tarjeta-encabezado">
        <div>
            <h2 id="titulo-estado" class="tarjeta-titulo">Estado de la cadena</h2>
            <p class="tarjeta-sub">Indicador principal de cada estación contra su meta · últimos 30 días</p>
        </div>
        <div class="leyenda" aria-hidden="true">
            <span class="leyenda-item"><span class="leyenda-linea"></span>Real</span>
            <span class="leyenda-item"><span class="leyenda-linea leyenda-meta"></span>Meta</span>
        </div>
    </div>
    <div class="estaciones" id="estaciones" aria-live="polite"></div>
</section>

<div class="row g-3 mt-0">
    <div class="col-12 col-xl-5">
        <section class="tarjeta h-100" aria-labelledby="titulo-atender">
            <div class="tarjeta-encabezado">
                <div>
                    <h2 id="titulo-atender" class="tarjeta-titulo">Qué atender hoy</h2>
                    <p class="tarjeta-sub">Prioridad por impacto esperado en MXN · recomendaciones de la IA</p>
                </div>
                <span class="contador" id="atender-contador"></span>
            </div>
            <ol class="atender" id="atender"></ol>
            <p class="texto-suave" id="atender-vacio" hidden>No hay recomendaciones abiertas.</p>
        </section>
    </div>
    <div class="col-12 col-xl-7">
        <section class="tarjeta h-100" aria-labelledby="titulo-demanda">
            <div class="tarjeta-encabezado">
                <div>
                    <h2 id="titulo-demanda" class="tarjeta-titulo">Demanda y pronóstico</h2>
                    <p class="tarjeta-sub" id="demanda-sub">Unidades diarias, todos los SKU</p>
                </div>
                <dl class="cifras">
                    <div><dt>Próximos 14 días</dt><dd id="demanda-total">–</dd></div>
                    <div><dt>MAPE</dt><dd id="demanda-mape">–</dd></div>
                </dl>
            </div>
            <div class="grafica-demanda">
                <canvas id="grafica-demanda" role="img" aria-label="Demanda real de los últimos 28 días y pronóstico de 14 días con intervalo de 90 %"></canvas>
            </div>
            <div class="leyenda leyenda-pie">
                <span class="leyenda-item"><span class="leyenda-linea"></span>Real</span>
                <span class="leyenda-item"><span class="leyenda-linea leyenda-pronostico"></span>Pronóstico</span>
                <span class="leyenda-item"><span class="leyenda-banda"></span>Intervalo 90 %</span>
                <span class="leyenda-nota" id="demanda-variacion"></span>
            </div>
        </section>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js"
        integrity="sha256-SERKgtTty1vsDxll+qzd4Y2cF9swY9BCq62i9wXJ9Uo=" crossorigin="anonymous"></script>
<script src="${pageContext.request.contextPath}/js/comun.js?v=${sc:esc(version)}"></script>
<script src="${pageContext.request.contextPath}/js/vivo.js?v=${sc:esc(version)}"></script>
<script src="${pageContext.request.contextPath}/js/resumen.js?v=${sc:esc(version)}"></script>

<%@ include file="/WEB-INF/jsp/fragmentos/pie.jspf" %>