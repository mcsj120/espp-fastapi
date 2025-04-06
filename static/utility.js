// Copied from r2r code, request.js
async function sendGetRequest(url){
    let response = await fetch(url, {
        method : "GET"
    })
    let text = await response.json()
    return text;
}

async function sendGetRequestFile(url) {
    let response = await fetch(url, {
        method: "GET"
    });
    if (response.status === 200) {
        let blob = await response.blob();
        let urlBlob = window.URL.createObjectURL(blob);
        let a = document.createElement('a');
        a.href = urlBlob;
        a.download = 'time_series_data.csv'; // You can set the file name here
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(urlBlob);
    } else {
        let text = await response.json()
        return text;
    }
}

async function sendPostRequest(url, data){
    let response = await fetch(url, {
        method : "POST",
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    let text = await response.json()
    return text
}

// Function to set a cookie
function setCookie(name, value, days) {
    const d = new Date();
    d.setTime(d.getTime() + (days * 24 * 60 * 60 * 1000));
    let expires = "expires=" + d.toUTCString();
    document.cookie = name + "=" + value + ";" + expires + ";path=/";
}

// Function to get a cookie
function getCookie(name) {
    let nameEQ = name + "=";
    let ca = document.cookie.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}