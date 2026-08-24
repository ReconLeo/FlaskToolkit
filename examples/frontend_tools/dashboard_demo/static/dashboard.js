/* dashboard_demo 前端工具静态资源：加载数据 + ECharts 渲染 */
async function loadAll() {
    try {
        const [infoResp, statsResp] = await Promise.all([
            fetch('/api/admin/system/info'),
            fetch('/api/admin/stats'),
        ]);
        const infoData = await infoResp.json();
        const statsData = await statsResp.json();
        const info = infoData.data || {};
        const stats = statsData.data || {};

        // 顶部统计卡片
        const cards = [
            { num: info.framework_version || '-', label: '框架版本' },
            { num: info.total_plugins_catalog ?? '-', label: '插件目录' },
            { num: info.total_frontend_tools ?? '-', label: '前端工具' },
            { num: info.total_calls ?? '-', label: '累计调用' },
            { num: info.python_version || '-', label: 'Python' },
        ];
        document.getElementById('cards').innerHTML = cards.map(c =>
            `<div class="stat-card"><div class="num">${c.num}</div><div class="label">${c.label}</div></div>`
        ).join('');

        // 系统信息
        const sys = [
            `平台：${info.platform || '-'}`,
            `基础目录：${info.base_dir || '-'}`,
            `绑定地址：${info.host || '-'}`,
            `调试模式：${info.debug ? '开启' : '关闭'}`,
            `内置插件：${(info.builtin_plugins || []).join('、') || '-'}`,
            `API 调用：${info.total_api_calls ?? '-'} · 前端工具访问：${info.total_frontend_access ?? '-'}`,
        ].map(s => `<div>${s}</div>`).join('');
        document.getElementById('sysInfo').innerHTML = sys;

        // 各插件调用统计（ECharts 柱状图）
        renderChart(stats);
    } catch (e) {
        document.getElementById('sysInfo').textContent = '加载失败：' + e.message;
    }
}

function renderChart(stats) {
    const el = document.getElementById('chart');
    if (typeof echarts === 'undefined') {
        el.innerHTML = '<p style="color:#95a5a6;">ECharts 未加载（CDN 不可达时请将 echarts.min.js 下载到 static/ 目录）。</p>';
        return;
    }
    // stats 结构：{ 插件名: 调用次数, ... }（来自 GET /api/admin/stats）
    const callStats = stats.call_stats || stats || {};
    const entries = Object.entries(callStats)
        .filter(([, v]) => typeof v === 'number')
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);
    if (!entries.length) {
        el.innerHTML = '<p style="color:#95a5a6;">暂无调用统计数据。</p>';
        return;
    }
    const chart = echarts.init(el);
    chart.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: 90, right: 20, bottom: 30, top: 20 },
        xAxis: { type: 'value' },
        yAxis: { type: 'category', data: entries.map(([k]) => k), inverse: true },
        series: [{
            type: 'bar',
            data: entries.map(([, v]) => v),
            itemStyle: { color: '#3498db' },
            label: { show: true, position: 'right' },
        }],
    });
}

// 首次加载
loadAll();
