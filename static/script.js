// ==========================================
// AI LIBRARY ASSISTANT - script.js
// ==========================================


// ---------- SEARCH BOOKS ----------

async function searchBooks() {
    const input = document.getElementById("searchInput");
    const resultsDiv = document.getElementById("searchResults");

    const query = input.value.trim();

    // Do not show the full collection when search is empty
    if (!query) {
        resultsDiv.innerHTML = "";
        return;
    }

    resultsDiv.innerHTML = `
        <div class="loading">
            🔍 Searching library...
        </div>
    `;

    try {
        const response = await fetch(
            `/api/search?q=${encodeURIComponent(query)}`
        );

        const books = await response.json();

        if (!books || books.length === 0) {
            resultsDiv.innerHTML = `
                <div class="no-results">
                    <h3>📚 No books found</h3>
                    <p>Try searching by Book ID, title, author, or keyword.</p>
                </div>
            `;
            return;
        }

        displayBooks(books);

    } catch (error) {
        console.error("Search error:", error);

        resultsDiv.innerHTML = `
            <div class="no-results">
                ❌ Unable to search the library.
                <br>
                Please try again.
            </div>
        `;
    }
}


// ---------- DISPLAY BOOKS ----------

function displayBooks(books) {
    const resultsDiv = document.getElementById("searchResults");

    let html = `
        <h2>📚 Search Results</h2>
        <div class="books-grid">
    `;

    books.forEach(book => {
        const available =
            Number(book.available_copies) > 0;

        html += `
            <div class="book-card">

                <div class="book-cover">
                    ${
                        book.cover_image
                        ? `<img src="${book.cover_image}" alt="${escapeHtml(book.title)}">`
                        : `📖`
                    }
                </div>

                <div class="book-info">

                    <h3>${escapeHtml(book.title)}</h3>

                    <p>
                        <strong>Book ID:</strong>
                        ${escapeHtml(book.book_id)}
                    </p>

                    <p>
                        <strong>Author:</strong>
                        ${escapeHtml(book.author)}
                    </p>

                    <p>
                        <strong>Category:</strong>
                        ${escapeHtml(book.main_category)}
                        ${
                            book.sub_category
                            ? ` → ${escapeHtml(book.sub_category)}`
                            : ""
                        }
                    </p>

                    <p>
                        <strong>ISBN:</strong>
                        ${escapeHtml(book.isbn)}
                    </p>

                    <p>
                        <strong>Language:</strong>
                        ${escapeHtml(book.language)}
                    </p>

                    <p>
                        <strong>Year:</strong>
                        ${escapeHtml(String(book.year))}
                    </p>

                    <p>
                        <strong>Edition:</strong>
                        ${escapeHtml(book.edition)}
                    </p>

                    <p>
                        <strong>Availability:</strong>

                        <span class="${available ? "available" : "unavailable"}">
                            ${
                                available
                                ? `Available (${book.available_copies} copies)`
                                : "Currently unavailable"
                            }
                        </span>
                    </p>

                    <p>
                        <strong>Shelf:</strong>
                        ${escapeHtml(book.shelf_location)}
                    </p>

                    <p>
                        <strong>Rating:</strong>
                        ⭐ ${escapeHtml(String(book.rating))}
                    </p>

                    <p>
                        <strong>Difficulty:</strong>
                        ${escapeHtml(book.difficulty_level)}
                    </p>

                    <p class="description">
                        ${escapeHtml(book.description)}
                    </p>

                </div>

            </div>
        `;
    });

    html += `</div>`;

    resultsDiv.innerHTML = html;
}


// ---------- AI CHAT ----------

async function sendMessage() {
    const input = document.getElementById("chatInput");
    const messagesDiv = document.getElementById("chatMessages");

    const message = input.value.trim();

    if (!message) {
        return;
    }

    // Show user's message
    addMessage(message, "user-message");

    input.value = "";

    // Show thinking message
    const thinking = document.createElement("div");
    thinking.className = "message bot-message";
    thinking.id = "thinkingMessage";
    thinking.innerHTML = "🤖 Thinking...";
    messagesDiv.appendChild(thinking);

    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    try {
        const response = await fetch("/api/chat", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: message
            })
        });

        const data = await response.json();

        // Remove thinking message
        const thinkingMessage =
            document.getElementById("thinkingMessage");

        if (thinkingMessage) {
            thinkingMessage.remove();
        }

        addMessage(
            data.reply || "Sorry, I could not understand that.",
            "bot-message"
        );

    } catch (error) {
        console.error("Chat error:", error);

        const thinkingMessage =
            document.getElementById("thinkingMessage");

        if (thinkingMessage) {
            thinkingMessage.remove();
        }

        addMessage(
            "❌ Sorry, I could not connect to the AI service right now.",
            "bot-message"
        );
    }
}


// ---------- ADD CHAT MESSAGE ----------

function addMessage(message, className) {
    const messagesDiv =
        document.getElementById("chatMessages");

    const messageDiv =
        document.createElement("div");

    messageDiv.className =
        `message ${className}`;

    // Convert basic Markdown formatting
    messageDiv.innerHTML =
        formatMessage(message);

    messagesDiv.appendChild(messageDiv);

    messagesDiv.scrollTop =
        messagesDiv.scrollHeight;
}


// ---------- FORMAT AI RESPONSE ----------

function formatMessage(message) {
    if (!message) {
        return "";
    }

    let text = escapeHtml(String(message));

    // Bold: **text**
    text = text.replace(
        /\*\*(.*?)\*\*/g,
        "<strong>$1</strong>"
    );

    // New lines
    text = text.replace(/\n/g, "<br>");

    return text;
}


// ---------- ENTER KEY FOR SEARCH ----------

document.addEventListener("DOMContentLoaded", function () {

    const searchInput =
        document.getElementById("searchInput");

    const chatInput =
        document.getElementById("chatInput");

    if (searchInput) {
        searchInput.addEventListener(
            "keydown",
            function (event) {
                if (event.key === "Enter") {
                    searchBooks();
                }
            }
        );
    }

    if (chatInput) {
        chatInput.addEventListener(
            "keydown",
            function (event) {
                if (event.key === "Enter") {
                    sendMessage();
                }
            }
        );
    }
});


// ---------- ESCAPE HTML ----------
// Prevents book data from being interpreted as HTML

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
