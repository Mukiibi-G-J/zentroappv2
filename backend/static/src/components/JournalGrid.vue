<template>
  <div class="journal-grid">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="left-actions">
        <button class="btn btn-primary" @click="post">
          <i class="fas fa-check"></i> Post
        </button>
        <button class="btn btn-secondary" @click="calculateAdjustment">
          <i class="fas fa-calculator"></i> Calculate Warehouse Adjustment
        </button>
        <button class="btn btn-secondary" @click="print">
          <i class="fas fa-print"></i> Print
        </button>
        <button class="btn btn-secondary" @click="getStandardJournals">
          <i class="fas fa-book"></i> Get Standard Journals
        </button>
        <button class="btn btn-secondary" @click="recalculateAmount">
          <i class="fas fa-sync"></i> Recalculate Unit Amount
        </button>
        <button class="btn btn-secondary" @click="explodeBOM">
          <i class="fas fa-sitemap"></i> Explode BOM
        </button>
      </div>
    </div>

    <!-- Grid -->
    <ag-grid-vue
      class="ag-theme-alpine"
      :columnDefs="columnDefs"
      :rowData="rowData"
      :defaultColDef="defaultColDef"
      @cell-value-changed="onCellValueChanged"
      @grid-ready="onGridReady"
      :editType="'fullRow'"
      :suppressClickEdit="true"
      rowSelection="multiple"
    >
    </ag-grid-vue>

    <!-- Add Row Button -->
    <div class="grid-actions">
      <button class="btn btn-sm btn-primary" @click="addNewRow">
        <i class="fas fa-plus"></i> Add Row
      </button>
    </div>
  </div>
</template>

<script>
import { AgGridVue } from "ag-grid-vue3";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import { ref, onMounted } from "vue";

export default {
  name: "JournalGrid",
  components: {
    AgGridVue,
  },
  created() {
    console.log("JournalGrid component created");
  },
  mounted() {
    console.log("JournalGrid component mounted");
  },
  props: {
    journalType: {
      type: String,
      required: true,
    },
  },
  setup(props) {
    const gridApi = ref(null);
    const columnDefs = [
      {
        headerName: "Posting Date",
        field: "postingDate",
        editable: true,
        cellEditor: "datePicker",
        width: 120,
      },
      {
        headerName: "Entry Type",
        field: "entryType",
        editable: true,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: {
          values: [
            "Purchase",
            "Sale",
            "PositiveAdjustment",
            "NegativeAdjustment",
          ],
        },
        width: 120,
      },
      {
        headerName: "Document No.",
        field: "documentNo",
        editable: true,
        width: 130,
      },
      {
        headerName: "Item No.",
        field: "itemNo",
        editable: true,
        cellEditor: "agTextCellEditor",
        width: 120,
      },
      {
        headerName: "Description",
        field: "description",
        editable: true,
        width: 200,
      },
      {
        headerName: "Location Code",
        field: "locationCode",
        editable: true,
        width: 120,
      },
      {
        headerName: "Bin Code",
        field: "binCode",
        editable: true,
        width: 100,
      },
      {
        headerName: "Quantity",
        field: "quantity",
        editable: true,
        type: "numericColumn",
        width: 100,
      },
      {
        headerName: "Unit of Measure",
        field: "unitOfMeasure",
        editable: true,
        width: 120,
      },
      {
        headerName: "Unit Amount",
        field: "unitAmount",
        editable: true,
        type: "numericColumn",
        width: 110,
      },
      {
        headerName: "Amount",
        field: "amount",
        editable: true,
        type: "numericColumn",
        width: 110,
      },
      {
        headerName: "Discount Amount",
        field: "discountAmount",
        editable: true,
        type: "numericColumn",
        width: 120,
      },
      {
        headerName: "Unit Cost",
        field: "unitCost",
        editable: true,
        type: "numericColumn",
        width: 100,
      },
      {
        headerName: "Applies-to Entry",
        field: "appliestoEntry",
        editable: true,
        width: 120,
      },
      {
        headerName: "Department Code",
        field: "departmentCode",
        editable: true,
        width: 130,
      },
      {
        headerName: "Area Code",
        field: "areaCode",
        editable: true,
        width: 100,
      },
    ];

    const defaultColDef = {
      sortable: true,
      filter: true,
      resizable: true,
    };

    const rowData = ref([
      {
        postingDate: new Date(),
        entryType: "",
        documentNo: "",
        itemNo: "",
        description: "",
        locationCode: "",
        binCode: "",
        quantity: 0,
        unitOfMeasure: "",
        unitAmount: 0,
        amount: 0,
        discountAmount: 0,
        unitCost: 0,
        appliestoEntry: "",
        departmentCode: "",
        areaCode: "",
      },
    ]);

    const onGridReady = (params) => {
      gridApi.value = params.api;
    };

    const addNewRow = () => {
      const newRow = {
        postingDate: new Date(),
        entryType: "",
        documentNo: "",
        // ... other fields with default values
      };
      gridApi.value.applyTransaction({ add: [newRow] });
    };

    const onCellValueChanged = (params) => {
      console.log("Cell changed:", params);
    };

    // Toolbar methods
    const post = () => {
      const selectedRows = gridApi.value.getSelectedRows();
      this.$emit("post", selectedRows);
    };

    const calculateAdjustment = () => {
      // Implement warehouse adjustment calculation
    };

    const print = () => {
      // Implement print functionality
    };

    const getStandardJournals = () => {
      // Implement getting standard journals
    };

    const recalculateAmount = () => {
      // Implement amount recalculation
    };

    const explodeBOM = () => {
      // Implement BOM explosion
    };

    return {
      columnDefs,
      defaultColDef,
      rowData,
      onGridReady,
      addNewRow,
      onCellValueChanged,
      post,
      calculateAdjustment,
      print,
      getStandardJournals,
      recalculateAmount,
      explodeBOM,
    };
  },
};
</script>

<style scoped>
.journal-grid {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.toolbar {
  padding: 0.5rem;
  background-color: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 4px;
}

.left-actions {
  display: flex;
  gap: 0.5rem;
}

.ag-theme-alpine {
  height: 500px;
  width: 100%;
}

.grid-actions {
  padding: 0.5rem;
  display: flex;
  justify-content: flex-start;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  font-size: 0.875rem;
  border-radius: 0.25rem;
  cursor: pointer;
}

.btn-primary {
  background-color: #007bff;
  color: white;
  border: 1px solid #0056b3;
}

.btn-secondary {
  background-color: #6c757d;
  color: white;
  border: 1px solid #545b62;
}
</style>
