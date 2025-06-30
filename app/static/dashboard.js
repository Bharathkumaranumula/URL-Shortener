const shortCode = new URLSearchParams(window.location.search).get('code');
document.getElementById("code").innerText = shortCode;

fetch(`/analytics/${shortCode}`)
    .then(res => res.json())
    .then(data => {
        document.getElementById("clicks").innerText = data.total_clicks;

        const countries = data.by_country.map(c => c.country);
        const clicks = data.by_country.map(c => c.clicks);

        const referrers = data.by_referrer.map(r => r.referrer);
        const refClicks = data.by_referrer.map(r => r.clicks);

        new Chart(document.getElementById("countryChart"), {
            type: 'pie',
            data: {
                labels: countries,
                datasets: [{
                    label: 'Clicks by Country',
                    data: clicks,
                    backgroundColor: ['#ff6384', '#36a2eb', '#cc65fe']
                }]
            }
        });

        new Chart(document.getElementById("referrerChart"), {
            type: 'bar',
            data: {
                labels: referrers,
                datasets: [{
                    label: 'Clicks by Referrer',
                    data: refClicks,
                    backgroundColor: '#4bc0c0'
                }]
            }
        });
    });
