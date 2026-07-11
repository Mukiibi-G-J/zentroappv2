class DeleteDialog {
    /**
     * Creates an instance of DeleteDialog
     * @constructor
     * @description Initializes the delete dialog and sets up required DOM elements
     */
    constructor() {
        this.dialog = document.getElementById('deleteDialog');
        this.deleteForm = document.getElementById('deleteForm');
        this.itemNameSpan = document.getElementById('deleteItemName');
        // initialize whne an object of this class is created
        this.init()
    }

    init() {
        this.dialog.addEventListener('show.bs.modal', (event) => {
            const button = event.relatedTarget
            /**
             * The .dataset property is used to access the data attributes of the button element
             * with the data-item-id, data-item-name, and data-delete-url attributes
             */
            const itemId = button.dataset.itemId;
            const itemName = button.dataset.itemName
            const deleteUrl = button.dataset.deleteUrl


            this.itemNameSpan.textContent = itemName
            this.deleteForm.action = deleteUrl;
        });
    }
    /**
     * Creates and initializes a new DeleteDialog instance
     * @static
     * @method initialize
     * @returns {DeleteDialog} New DeleteDialog instance
    */
    static initialize() {
        return new DeleteDialog();
    }
}