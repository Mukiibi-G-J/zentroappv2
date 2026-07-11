class Pos {
    constructor() {
        this.initializeElements()
        this.initializeState()
        this.setupEventListeners()
        // this.fetchSalesSetup()
    }

    initializeElements() {
        this.searchInput = document.getElementById("itemSearch")
        this.searchResults = document.getElementById("searchResults")
        this.searchSpinner = document.getElementById("searchSpinner")
        this.searchResultsContent = document.getElementById("searchResultsContent")


        // payment elements
        this.paymentModal = document.getElementById('paymentModal')
        this.editItemModal = document.getElementById('editModal')
        this.openPaymentModalBtn = document.getElementById('openPaymentModalBtn')
        this.amountReceived = document.getElementById('amountReceived')
        this.changeAmount = document.getElementById('changeAmount')
        this.modalTotalAmount = document.getElementById('modalTotalAmount')
        this.completeSaleBtn = document.getElementById('completeSaleBtn')
        this.cartTableBody = document.getElementById('cartTableBody')
        this.cartTotal = document.getElementById('cartTotal');
        this.paymentModal = new bootstrap.Modal(document.getElementById('paymentModal'))


    }

    initializeState() {
        this.cartItems = []
        this.debounceTimer = null
        this.salesSetup = {
            enableEditPrice: false,
            enableEditDate: false,
        }
        console.log(new bootstrap.Modal(document.getElementById('paymentModal')))
    }


    setupEventListeners() {
        this.searchInput.addEventListener('input', this.handleSearchInput.bind(this))
        document.addEventListener('click', this.handleClickOutSide.bind(this))
        document.addEventListener('click', this.handleItemSelection.bind(this))
        document.addEventListener('keydown', this.handleKeyBoardShortcuts.bind(this))

        // Cart listeners
        if (this.cartTableBody) {
            this.cartTableBody.addEventListener('click', this.handleQuantityChange.bind(this));
        }

        // Payment Listeners
        this.openPaymentModalBtn.addEventListener('click', this.handleOpenPaymentModal.bind(this));

        // this.paymentModal.addEventListener('show.bs.modal', this.handleOpenPaymentModal.bind(this));
        // this.paymentModal.addEventListener('click', this.handleOpenPaymentModal.bind(this));
        if (this.amountReceived) {
            this.amountReceived.addEventListener('input', this.handleAmountReceivedInput.bind(this));
        }
        this.completeSaleBtn.addEventListener('click', this.handleCompleteSale.bind(this));


    }

    async handleSearchInput(e) {
        clearTimeout(this.debounceTimer)
        this.debounceTimer = setTimeout(() => {
            this.handleSearch(e.target.value)
        })
    }

    async handleSearch(searchTerm) {
        console.log(searchTerm.trim())

        // !("   ".trim()) Returns true   (because "" is empty)
        // !("".trim()) Returns true  (because "" is empty)
        // !("abc".trim()) Returns false (because "abc" is not empty)
        if (!searchTerm.trim()) {
            this.searchResults.classList.add('hidden')
            return;
        }

        try {
            this.toggleSearchUI(true)
            const data = await this.fetchSearchResults(searchTerm)
            this.renderSearchResults(data.results)
        } catch { }

    }


    async fetchSearchResults(searchTerm) {
        const response = await fetch(`/api/items/filter?q=${encodeURIComponent(searchTerm)}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        }
        )

        if (!response.ok) {
            throw new Error('Failed to fetch search results')
        }

        const data = await response.json()
        return data
    }
    toggleSearchUI(isSearching) {
        if (isSearching) {
            this.searchResults.classList.remove('hidden');
            this.searchSpinner.classList.remove('hidden');
            this.searchResultsContent.innerHTML = '';
        } else {
            this.searchSpinner.classList.add('hidden');
        }
    }

    renderSearchResults(results) {
        this.toggleSearchUI(false)
        if (results.length === 0) {
            this.renderEmptySearchResults()
            return
        }
        //1. ['<div class="product-item">Product 1</div>','<div class="product-item">Product 2</div>','<div class="product-item">Product 3</div>']
        // 2. Then join('') combines them into one string with new lines
        this.searchResultsContent.innerHTML = results.map(item => this.createItemHTML(item)).join('');
    }

    renderEmptySearchResults() {
        this.searchResultsContent.innerHTML = `<div class="p-4 text-center text-gray-500"> No items found  </div>`

    }
    createItemHTML(item) {
        return `
            <div class="item-item p-4 hover:bg-gray-50 cursor-pointer flex justify-between items-center border-b last:border-b-0"
                 data-item-system-id="${item.system_id}"
                 data-item-name="${item.item_name}"
                 data-item-price="${item.unit_price}"
                 data-item-stock="${item.inventory}"
                 data-item-no="${item.no}">
                <div>
                    <div class="font-medium">${item.item_name}</div>
                    <div class="text-sm text-gray-600">Stock: ${item.inventory}</div>
                </div>
                <div class="text-blue-600 font-medium">UGX ${item.unit_price.toLocaleString()}</div>
            </div>
        `;
    }

    handleItemSelection(e) {
        const item = e.target.closest(".item-item")
        if (!item) return

        const itemData = {
            system_id: item.dataset.itemSystemId,
            name: item.dataset.itemName,
            price: item.dataset.itemPrice,
            stock: item.dataset.itemStock,
            no: item.dataset.itemNo,
        }

        console.log(itemData)
        this.addItemToCart(itemData)
        this.searchResults.classList.add('hidden')
        this.searchInput.value = ""
    }

    addItemToCart(itemData) {

        const existingItem = this.cartItems.find(item => item.system_id === itemData.system_id);

        if (existingItem) {
            existingItem.quantity += 1;
            existingItem.total = existingItem.quantity * existingItem.price;
        } else {
            this.cartItems.push({
                system_id: itemData.system_id,
                name: itemData.name,
                price: parseInt(itemData.price),
                quantity: 1,
                total: parseInt(itemData.price),
                no: itemData.no,
                stock: parseInt(itemData.stock),
            });

        }
        this.updateCart()
    }

    updateCart() {
        this.updateCartTable()
        this.calculateCartTotal()
        this.updateCompleteButton()
    }

    updateCartTable() {
        if (!this.cartTableBody) {
            console.warn('Cart table body element not found');
            return;
        }

        this.cartTableBody.innerHTML = this.cartItems.map((item, index) => `
                <tr class="border-b border-gray-200 dark:border-gray-600">
                    <td class="py-3 px-4">${index + 1}</td>
                    <td class="py-3 px-4">${item.name}</td>
                    <td class="py-3 px-4">UGX ${item.price.toLocaleString()}</td>
                    <td class="py-3 px-4">
                        <div class="flex items-center gap-2">
                            <button class="quantity-btn" data-system-id="${item.system_id}" data-action="decrease">-</button>
                            <span>${item.quantity}</span>
                            <button class="quantity-btn" data-system-id="${item.system_id}" data-action="increase">+</button>
                        </div>
                    </td>
                    <td class="py-3 px-4">UGX ${item.total.toLocaleString()}</td>
                    <td class="py-3 px-4">
                        <div class="flex items-center gap-2">
                            ${(this.salesSetup.enableEditPrice || this.salesSetup.enableEditDate) ? `
                                <button class="edit-item-btn text-blue-500 hover:text-blue-700" data-id="${item.system_id}">
                                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                    </svg>
                                </button>
                            ` : ''}
                            <button class="text-red-500 hover:text-red-700" onclick="pos.removeFromCart('${item.system_id}')">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
    };

    calculateCartTotal() {

        const total = this.cartItems.reduce((sum, item) => sum + item.total, 0);

        if (!this.cartTotal) {
            console.warn('Cart total element not found');
            return;
        }

        this.cartTotal.textContent = `UGX ${total.toLocaleString()}`;
    }

    handleClickOutSide(e) {
        if (!this.searchResults.contains(e.target)) {
            this.searchResults.classList.add('hidden')
        }
    }

    removeFromCart(system_id) {
        this.cartItems = this.cartItems.filter(item => item.system_id !== system_id)
        this.updateCart()
    }

    handleQuantityChange(e) {
        const btn = e.target.closest('.quantity-btn')
        const action = btn.dataset.action
        const itemSystemId = btn.dataset.systemId

        const item = this.cartItems.find(item => item.system_id === itemSystemId)
        // console.log(item)

        if (!item) return
        console.log(item)
        console.log(action)

        if (action === 'decrease' && item.quantity > 1) {
            item.quantity -= 1
            item.total = item.quantity * item.price
        } else if (action === 'increase' && parseInt(item.quantity) < parseInt(item.stock)) {
            item.quantity += 1
            item.total = item.quantity * item.price
        }
        this.updateCart()
    }

    handleCompleteSale() {

        this.paymentModal.hide();
        this.cartTotal.textContent = 'UGX 0';
        this.cartItems = []
        this.updateCart()
    }

    handleOpenPaymentModal() {
        const total = this.cartItems.reduce((sum, item) => sum + item.total, 0);
        this.modalTotalAmount.textContent = `UGX ${total.toLocaleString()}`;
        this.amountReceived.value = '';
        this.changeAmount.textContent = 'UGX 0';
        this.paymentModal.show();
        // Wait for modal to be fully shown before focusing
        this.amountReceived.focus();


    }

    handleAmountReceivedInput(e) {
        let value = e.target.value.replace(/[^0-9]/g, '')
        if (value) {
            // Convert to number and format with commas
            value = parseInt(value).toLocaleString()
            e.target.value = value
        }
        this.calucalteChange()
    }

    calucalteChange() {
        const total = this.cartItems.reduce((sum, item) => sum + item.total, 0);
        const amountReceived = parseInt(this.amountReceived.value.replace(/[^0-9]/g, '')) || 0;
        const change = amountReceived - total;
        this.changeAmount.textContent = `UGX ${change.toLocaleString()}`;
        this.completeSaleBtn.disabled = amountReceived < total;

    }

    updateCompleteButton() {
        if (this.openPaymentModalBtn) {
            this.openPaymentModalBtn.disabled = this.cartItems.length === 0;
        }
    }

    handleKeyBoardShortcuts(e) {
        if (e.key === 'F2') {
            e.preventDefault();
            if (!this.openPaymentModalBtn.disabled) {
                this.openPaymentModalBtn.click();

                // auto focus the input with id -> amountReceived
                this.amountReceived.focus()
                console.log(this.amountReceived)
            }
        } else if (e.key === 'Escape') {
            this.paymentModal.hide();
        } else if (e.key === 'Enter' && document.activeElement === this.amountReceived) {
            if (!this.completeSaleBtn.disabled) {
                this.completeSaleBtn.click();
            }
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    pos = new Pos()
})
