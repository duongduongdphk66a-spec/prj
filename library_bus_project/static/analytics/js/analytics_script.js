// analytics/static/analytics/js/analytics_common.js

// Common chart configuration
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            display: true,
            position: 'top'
        }
    },
    scales: {
        y: {
            beginAtZero: true
        }
    }
};

// Chart colors
const chartColors = {
    primary: 'rgba(74, 108, 247, 1)',
    primaryLight: 'rgba(74, 108, 247, 0.1)',
    success: 'rgba(22, 163, 74, 1)',
    successLight: 'rgba(22, 163, 74, 0.1)',
    warning: 'rgba(251, 146, 60, 1)',
    warningLight: 'rgba(251, 146, 60, 0.1)',
    danger: 'rgba(239, 68, 68, 1)',
    dangerLight: 'rgba(239, 68, 68, 0.1)',
    info: 'rgba(59, 130, 246, 1)',
    infoLight: 'rgba(59, 130, 246, 0.1)'
};

// Level distribution colors
const levelColors = {
    bronze: '#CD7F32',
    silver: '#C0C0C0',
    gold: '#FFD700',
    platinum: '#E5E4E2',
    diamond: '#B9F2FF'
};

// Analytics Charts Class
class AnalyticsCharts {
    constructor() {
        this.charts = {};
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.initializeCharts();
        });
    }

    initializeCharts() {
        // Initialize all charts based on available canvas elements
        this.initActivityChart();
        this.initLevelDistributionChart();
        this.initBorrowHistoryChart();
        this.initBusPerformanceChart();
        this.initReportsChart();
    }

    // Activity chart for admin dashboard
    initActivityChart() {
        const ctx = document.getElementById('activityChart');
        if (!ctx || !window.weeklyStatsData) return;

        this.charts.activity = new Chart(ctx, {
            type: 'line',
            data: window.weeklyStatsData,
            options: {
                ...chartDefaults,
                plugins: {
                    ...chartDefaults.plugins,
                    title: {
                        display: true,
                        text: 'Hoạt động 4 tuần qua'
                    }
                }
            }
        });
    }

    // Level distribution chart for admin dashboard
    initLevelDistributionChart() {
        const ctx = document.getElementById('levelDistributionChart');
        if (!ctx || !window.levelDistributionData) return;

        this.charts.levelDistribution = new Chart(ctx, {
            type: 'doughnut',
            data: window.levelDistributionData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Phân bố người dùng theo cấp độ'
                    }
                }
            }
        });
    }

    // Borrow history chart for book detail analytics
    initBorrowHistoryChart() {
        const ctx = document.getElementById('borrowHistoryChart');
        if (!ctx || !window.borrowHistoryData) return;

        this.charts.borrowHistory = new Chart(ctx, {
            type: 'line',
            data: window.borrowHistoryData,
            options: {
                ...chartDefaults,
                plugins: {
                    ...chartDefaults.plugins,
                    title: {
                        display: true,
                        text: 'Lịch sử mượn sách 30 ngày qua'
                    }
                }
            }
        });
    }

    // Bus performance chart
    initBusPerformanceChart() {
        const ctx = document.getElementById('busPerformanceChart');
        if (!ctx || !window.busPerformanceData) return;

        this.charts.busPerformance = new Chart(ctx, {
            type: 'bar',
            data: window.busPerformanceData,
            options: {
                ...chartDefaults,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                },
                plugins: {
                    ...chartDefaults.plugins,
                    title: {
                        display: true,
                        text: 'Biểu đồ hiệu suất xe bus'
                    }
                }
            }
        });
    }

    // Reports chart
    initReportsChart() {
        const ctx = document.getElementById('reportsChart');
        if (!ctx || !window.reportsData) return;

        this.charts.reports = new Chart(ctx, {
            type: 'line',
            data: window.reportsData,
            options: {
                ...chartDefaults,
                plugins: {
                    ...chartDefaults.plugins,
                    title: {
                        display: true,
                        text: 'Thống kê hoạt động theo thời gian'
                    }
                }
            }
        });
    }

    // Destroy all charts
    destroy() {
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.charts = {};
    }
}

// Common utility functions
class AnalyticsUtils {
    // Refresh recommendations
    static refreshRecommendations() {
        const button = event.target;
        const originalHTML = button.innerHTML;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang tải...';
        button.disabled = true;

        setTimeout(() => {
            window.location.reload();
        }, 500);
    }

    // Borrow book function
    static borrowBook(bookId) {
        if (confirm('Bạn có muốn mượn sách này không?')) {
            // TODO: Implement actual book borrowing logic
            alert('Tính năng mượn sách đang được phát triển!');
        }
    }

    // Export report function
    static exportReport(format) {
        const params = new URLSearchParams(window.location.search);
        params.set('export', format);
        window.location.href = '?' + params.toString();
    }

    // Filter table rows
    static filterTable(filterValue) {
        const table = document.querySelector('.custom-table tbody');
        if (!table) return;

        const rows = table.querySelectorAll('tr');
        rows.forEach(row => {
            if (filterValue === 'all') {
                row.style.display = '';
            } else {
                const statusCell = row.querySelector('.badge');
                if (statusCell) {
                    const isActive = statusCell.textContent.includes('Hoạt động');
                    const shouldShow = (filterValue === 'active' && isActive) || 
                                     (filterValue === 'inactive' && !isActive);
                    row.style.display = shouldShow ? '' : 'none';
                }
            }
        });
    }

    // Format number with commas
    static formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    // Calculate percentage
    static calculatePercentage(value, total) {
        return total > 0 ? ((value / total) * 100).toFixed(1) : 0;
    }

    // Update progress bar
    static updateProgressBar(selector, percentage) {
        const progressBar = document.querySelector(selector);
        if (progressBar) {
            progressBar.style.width = percentage + '%';
        }
    }
}

// Event handlers
class AnalyticsEvents {
    constructor() {
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.bindEvents();
        });
    }

    bindEvents() {
        // Filter buttons for bus analytics
        this.bindFilterButtons();
        
        // Refresh buttons
        this.bindRefreshButtons();
        
        // Export buttons
        this.bindExportButtons();
        
        // Borrow buttons
        this.bindBorrowButtons();
    }

    bindFilterButtons() {
        const filterButtons = document.querySelectorAll('[data-filter]');
        filterButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                
                // Update active state
                filterButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                
                // Filter table
                const filterValue = button.getAttribute('data-filter');
                AnalyticsUtils.filterTable(filterValue);
            });
        });
    }

    bindRefreshButtons() {
        const refreshButtons = document.querySelectorAll('[onclick*="refreshRecommendations"]');
        refreshButtons.forEach(button => {
            button.removeAttribute('onclick');
            button.addEventListener('click', AnalyticsUtils.refreshRecommendations);
        });
    }

    bindExportButtons() {
        const exportButtons = document.querySelectorAll('[onclick*="exportReport"]');
        exportButtons.forEach(button => {
            const format = button.getAttribute('onclick').match(/'([^']+)'/)[1];
            button.removeAttribute('onclick');
            button.addEventListener('click', () => AnalyticsUtils.exportReport(format));
        });
    }

    bindBorrowButtons() {
        const borrowButtons = document.querySelectorAll('[onclick*="borrowBook"]');
        borrowButtons.forEach(button => {
            const bookId = button.getAttribute('onclick').match(/\d+/)[0];
            button.removeAttribute('onclick');
            button.addEventListener('click', () => AnalyticsUtils.borrowBook(bookId));
        });
    }
}

// Initialize everything
let analyticsCharts;
let analyticsEvents;

// Global initialization
document.addEventListener('DOMContentLoaded', function() {
    analyticsCharts = new AnalyticsCharts();
    analyticsEvents = new AnalyticsEvents();
});

// Make functions available globally for backward compatibility
window.refreshRecommendations = AnalyticsUtils.refreshRecommendations;
window.borrowBook = AnalyticsUtils.borrowBook;
window.exportReport = AnalyticsUtils.exportReport;

// Export classes for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        AnalyticsCharts,
        AnalyticsUtils,
        AnalyticsEvents
    };
}