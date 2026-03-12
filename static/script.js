// Form Validation Functions
document.addEventListener('DOMContentLoaded', function() {
    
    // Login Form Validation
    const loginForm = document.querySelector('.login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            const username = document.getElementById('username');
            const password = document.getElementById('password');
            
            if (username.value.trim() === '') {
                alert('Please enter username');
                username.focus();
                e.preventDefault();
                return false;
            }
            
            if (password.value.trim() === '') {
                alert('Please enter password');
                password.focus();
                e.preventDefault();
                return false;
            }
        });
    }
    
    // Product Form Validation
    const productForm = document.querySelector('#add_product') ? document.querySelector('.data-form') : null;
    if (productForm && productForm.querySelector('#name')) {
        productForm.addEventListener('submit', function(e) {
            const name = document.getElementById('name');
            const quantity = document.getElementById('quantity');
            const price = document.getElementById('price');
            
            if (name.value.trim() === '') {
                alert('Please enter product name');
                name.focus();
                e.preventDefault();
                return false;
            }
            
            if (parseInt(quantity.value) < 0) {
                alert('Quantity cannot be negative');
                quantity.focus();
                e.preventDefault();
                return false;
            }
            
            if (parseFloat(price.value) < 0) {
                alert('Price cannot be negative');
                price.focus();
                e.preventDefault();
                return false;
            }
        });
    }
    
    // Order Form Validation
    const orderForm = document.getElementById('orderForm');
    if (orderForm) {
        orderForm.addEventListener('submit', function(e) {
            const productId = document.getElementById('product_id');
            const quantity = document.getElementById('quantity');
            
            if (productId.value === '') {
                alert('Please select a product');
                productId.focus();
                e.preventDefault();
                return false;
            }
            
            if (parseInt(quantity.value) < 1) {
                alert('Quantity must be at least 1');
                quantity.focus();
                e.preventDefault();
                return false;
            }
        });
    }
    
    // Supplier Form Validation
    const supplierForm = document.querySelector('#add_supplier') ? document.querySelector('.data-form') : null;
    if (supplierForm && supplierForm.querySelector('#name')) {
        supplierForm.addEventListener('submit', function(e) {
            const name = document.getElementById('name');
            
            if (name.value.trim() === '') {
                alert('Please enter supplier name');
                name.focus();
                e.preventDefault();
                return false;
            }
        });
    }
    
    // Delete confirmation
    const deleteLinks = document.querySelectorAll('.btn-danger');
    deleteLinks.forEach(link => {
        if (!link.hasAttribute('onclick')) {
            link.addEventListener('click', function(e) {
                if (!confirm('Are you sure you want to delete this item?')) {
                    e.preventDefault();
                    return false;
                }
            });
        }
    });
    
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.remove();
            }, 500);
        }, 5000);
    });
});

// Calculate total price for order (backup function)
function calculateOrderTotal() {
    const productSelect = document.getElementById('product_id');
    const quantityInput = document.getElementById('quantity');
    const totalPriceInput = document.getElementById('total_price');
    
    if (productSelect && quantityInput && totalPriceInput) {
        const selectedOption = productSelect.options[productSelect.selectedIndex];
        const price = parseFloat(selectedOption.dataset.price) || 0;
        const quantity = parseInt(quantityInput.value) || 0;
        
        const total = price * quantity;
        totalPriceInput.value = '$' + total.toFixed(2);
    }
}
