<%--
  Centro de soluciones (Modulo 6; diseno CC-10). Pestanas Abiertas, En curso y
  Resueltas; evidencia, opciones comparadas por costo total esperado (CC-19),
  explicacion, plan de accion y decisiones humanas. La JSP solo pinta la
  estructura; js/soluciones.js lee /api/recomendaciones (ApiLecturaServlet) y
  registra decisiones en /api/decisiones (DecisionServlet, con rol y CSRF).
--%>
<%@ page contentType="text/html; charset=UTF-8" pageEncoding="UTF-8" %>
<%@ include file="/WEB-INF/jsp/fragmentos/cabecera.jspf" %>

<header class="vista-encabezado">
    <div>
        <h1 class="titulo-vista">Centro de soluciones</h1>
        <p class="vista-sub">La IA detecta, compara opciones y recomienda; la decisión y la ejecución son humanas.</p>
    </div>
    <div class="vista-frescura">
        <span class="etiqueta-origen">Datos simulados</span>
        <span id="sol-corte" class="texto-suave"></span>
    </div>
</header>

<p class="aviso aviso-error" id="sol-error" role="alert" hidden></p>

<section class="indicadores" aria-label="Resumen del Centro de soluciones">
    <div class="indicador"><span class="indicador-etiqueta">Abiertas</span><span class="indicador-valor" id="ind-abiertas">–</span><span class="indicador-sub" id="ind-criticas"></span></div>
    <div class="indicador"><span class="indicador-etiqueta">Impacto en juego</span><span class="indicador-valor" id="ind-impacto">–</span><span class="indicador-sub">Costo evitable si se actúa</span></div>
    <div class="indicador"><span class="indicador-etiqueta">Ahorro real, 90 días</span><span class="indicador-valor" id="ind-ahorro">–</span><span class="indicador-sub" id="ind-ahorro-sub"></span></div>
    <div class="indicador"><span class="indicador-etiqueta">Tiempo de decisión</span><span class="indicador-valor" id="ind-tiempo">–</span><span class="indicador-sub">Promedio de detección a decisión</span></div>
</section>

<div class="sol-cuerpo">
    <section class="tarjeta sol-lista-tarjeta" aria-label="Recomendaciones">
        <div class="pestanas" role="tablist" aria-label="Estado de las recomendaciones">
            <button type="button" role="tab" id="tab-abiertas" data-vista="abiertas" aria-selected="true">Abiertas <span class="pestana-n" id="n-abiertas"></span></button>
            <button type="button" role="tab" id="tab-en_curso" data-vista="en_curso" aria-selected="false">En curso <span class="pestana-n" id="n-en_curso"></span></button>
            <button type="button" role="tab" id="tab-resueltas" data-vista="resueltas" aria-selected="false">Resueltas <span class="pestana-n" id="n-resueltas"></span></button>
        </div>
        <ul class="sol-lista" id="sol-lista" role="tabpanel" aria-live="polite"></ul>
        <p class="texto-suave sol-vacio" id="sol-vacio" hidden></p>
    </section>

    <section class="tarjeta sol-detalle" id="sol-detalle" aria-live="polite">
        <p class="texto-suave" id="sol-sin-seleccion">Elige una recomendación de la lista para ver su evidencia, opciones y plan.</p>
        <div id="det" hidden>
            <div class="det-cabeza">
                <div>
                    <p class="det-meta" id="det-meta"></p>
                    <h2 class="det-titulo" id="det-titulo"></h2>
                </div>
                <div class="det-impacto">
                    <span class="det-impacto-etiqueta">Impacto estimado</span>
                    <span class="det-impacto-valor" id="det-impacto"></span>
                    <span id="det-severidad"></span>
                </div>
            </div>
            <p class="det-descripcion" id="det-descripcion"></p>

            <div class="det-seccion">
                <h3 class="det-subtitulo">Evidencia</h3>
                <div class="grafica-evidencia" id="det-grafica-caja">
                    <canvas id="det-grafica" role="img"></canvas>
                </div>
                <p class="texto-suave" id="det-grafica-nota"></p>
                <dl class="det-datos" id="det-datos"></dl>
            </div>

            <div class="det-seccion">
                <h3 class="det-subtitulo">Opciones comparadas por costo total esperado</h3>
                <p class="texto-suave" id="det-metodo"></p>
                <ul class="opciones" id="det-opciones"></ul>
            </div>

            <div class="det-seccion">
                <h3 class="det-subtitulo">Por qué se recomienda</h3>
                <p class="det-confianza" id="det-confianza"></p>
                <ul class="razones" id="det-razones"></ul>
                <details class="supuestos">
                    <summary>Supuestos económicos usados (CC-19)</summary>
                    <dl class="det-datos" id="det-supuestos"></dl>
                </details>
            </div>

            <div class="det-seccion">
                <h3 class="det-subtitulo">Plan de acción</h3>
                <ol class="plan" id="det-plan"></ol>
            </div>

            <div class="det-seccion" id="det-resultado-caja" hidden>
                <h3 class="det-subtitulo">Resultado</h3>
                <dl class="det-datos" id="det-resultado"></dl>
            </div>

            <div class="det-seccion decision" id="det-decision" hidden>
                <h3 class="det-subtitulo">Decisión</h3>
                <p class="aviso aviso-error" id="dec-error" role="alert" hidden></p>
                <p class="aviso aviso-info" id="dec-ok" role="status" hidden></p>

                <div id="dec-nueva" hidden>
                    <p class="texto-suave" id="dec-nueva-texto"></p>
                    <div class="decision-botones">
                        <button type="button" class="boton boton-principal" id="btn-aprobar">Aprobar opción elegida</button>
                        <button type="button" class="boton boton-claro" id="btn-mostrar-descarte">Descartar</button>
                    </div>
                </div>

                <div id="dec-curso" hidden>
                    <label class="campo-etiqueta" for="dec-ahorro">Ahorro real medido (MXN)</label>
                    <div class="decision-fila">
                        <input id="dec-ahorro" class="campo" type="number" step="0.01" inputmode="decimal" placeholder="Ejemplo: 65000">
                        <button type="button" class="boton boton-principal" id="btn-cerrar">Cerrar con ahorro real</button>
                        <button type="button" class="boton boton-claro" id="btn-mostrar-descarte-2">Descartar</button>
                    </div>
                </div>

                <div id="dec-descarte" hidden>
                    <label class="campo-etiqueta" for="dec-motivo">Motivo del descarte (obligatorio)</label>
                    <textarea id="dec-motivo" class="campo" rows="3" maxlength="300"></textarea>
                    <div class="decision-botones">
                        <button type="button" class="boton boton-peligro" id="btn-descartar">Confirmar descarte</button>
                        <button type="button" class="boton boton-claro" id="btn-cancelar-descarte">Cancelar</button>
                    </div>
                </div>

                <p class="texto-suave" id="dec-sin-permiso" hidden>Solo el rol Ejecutivo puede aprobar, descartar o cerrar recomendaciones.</p>
            </div>

            <div class="det-seccion" id="det-historial-caja" hidden>
                <h3 class="det-subtitulo">Historial de decisiones</h3>
                <ol class="historial" id="det-historial"></ol>
            </div>

            <p class="det-aviso">La IA puede equivocarse: revisa la evidencia antes de decidir. Ninguna compra se ejecuta desde el dashboard.</p>
        </div>
    </section>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js"
        integrity="sha256-SERKgtTty1vsDxll+qzd4Y2cF9swY9BCq62i9wXJ9Uo=" crossorigin="anonymous"></script>
<script src="${pageContext.request.contextPath}/js/comun.js?v=${sc:esc(version)}"></script>
<script src="${pageContext.request.contextPath}/js/soluciones.js?v=${sc:esc(version)}"></script>

<%@ include file="/WEB-INF/jsp/fragmentos/pie.jspf" %>