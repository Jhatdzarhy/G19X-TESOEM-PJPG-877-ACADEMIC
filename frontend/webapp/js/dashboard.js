const API_BASE = "http://localhost:8000";

async function cargarOTIF() {
    const res = await fetch(`${API_BASE}/kpis/otif`);
    const data = await res.json();
    document.getElementById("kpi-otif").textContent = data.otif_pct + "%";
    document.getElementById("kpi-otif-detalle").textContent =
        `${data.entregas_a_tiempo} de ${data.total_entregadas} entregas a tiempo`;
}

async function cargarLeadTime() {
    const res = await fetch(`${API_BASE}/kpis/lead-time`);
    const data = await res.json();
    document.getElementById("kpi-leadtime").textContent = data.lead_time_dias_promedio;
}

async function cargarProveedores() {
    const res = await fetch(`${API_BASE}/kpis/proveedores`);
    const data = await res.json();
    const proveedores = data.proveedores;

    document.getElementById("kpi-proveedores-count").textContent = proveedores.length;

    const tbody = document.querySelector("#tabla-proveedores tbody");
    tbody.innerHTML = "";
    proveedores.forEach(p => {
        const fila = document.createElement("tr");
        fila.innerHTML = `<td>${p.nombre}</td><td>${p.pais}</td><td>${p.calificacion}</td>`;
        tbody.appendChild(fila);
    });

    const ctx = document.getElementById("chartProveedores");
    new Chart(ctx, {
        type: "bar",
        data: {
            labels: proveedores.map(p => p.nombre),
            datasets: [{
                label: "Calificación",
                data: proveedores.map(p => p.calificacion),
                backgroundColor: "rgba(13, 110, 253, 0.7)"
            }]
        },
        options: {
            scales: { y: { beginAtZero: true, max: 5 } }
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    cargarOTIF();
    cargarLeadTime();
    cargarProveedores();
});