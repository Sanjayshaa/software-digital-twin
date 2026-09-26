const express = require('express');
const app = express();

function calculateFee(amount) {
    return amount * 0.05;
}

app.get('/health', (req, res) => {
    res.json({ status: 'ok' });
});

module.exports = { app, calculateFee };
