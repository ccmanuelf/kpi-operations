<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center justify-space-between mb-4">
          <h1 class="text-h4">
            <v-icon class="mr-2">mdi-account-multiple</v-icon>
            {{ t('admin.users.title') }}
          </h1>
          <v-btn color="primary" @click="openCreateDialog">
            <v-icon left>mdi-plus</v-icon>
            {{ t('admin.users.addUser') }}
          </v-btn>
        </div>
      </v-col>
    </v-row>

    <!-- Filters -->
    <v-row class="mb-4">
      <v-col cols="12" md="4">
        <v-text-field
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          :label="t('admin.users.searchUsers')"
          variant="outlined"
          density="comfortable"
          clearable
          hide-details
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-select
          v-model="roleFilter"
          :items="roleOptions"
          :label="t('admin.users.filterByRole')"
          variant="outlined"
          density="comfortable"
          clearable
          hide-details
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-select
          v-model="statusFilter"
          :items="statusOptions"
          :label="t('admin.users.filterByStatus')"
          variant="outlined"
          density="comfortable"
          clearable
          hide-details
        />
      </v-col>
      <v-col cols="12" md="2">
        <v-btn variant="outlined" @click="refreshUsers" :loading="loading">
          <v-icon>mdi-refresh</v-icon>
        </v-btn>
      </v-col>
    </v-row>

    <!-- Users Table -->
    <v-card>
      <v-data-table
        :headers="headers"
        :items="filteredUsers"
        :loading="loading"
        :search="search"
        class="elevation-1"
      >
        <template v-slot:item.is_active="{ item }">
          <v-chip :color="item.is_active ? 'success' : 'error'" size="small">
            {{ item.is_active ? t('admin.users.active') : t('admin.users.inactive') }}
          </v-chip>
        </template>

        <template v-slot:item.role="{ item }">
          <v-chip :color="getRoleColor(item.role)" size="small">
            {{ formatRole(item.role) }}
          </v-chip>
        </template>

        <template v-slot:item.created_at="{ item }">
          {{ formatDate(item.created_at) }}
        </template>

        <template v-slot:item.actions="{ item }">
          <v-btn icon size="small" variant="text" @click="editUser(item)">
            <v-icon>mdi-pencil</v-icon>
          </v-btn>
          <v-btn icon size="small" variant="text" @click="toggleUserStatus(item)">
            <v-icon>{{ item.is_active ? 'mdi-account-off' : 'mdi-account-check' }}</v-icon>
          </v-btn>
          <v-btn icon size="small" variant="text" color="error" @click="confirmDelete(item)">
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </template>
      </v-data-table>
    </v-card>

    <!-- Create/Edit User Dialog -->
    <v-dialog v-model="userDialog" max-width="600">
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">{{ editingUser ? 'mdi-pencil' : 'mdi-plus' }}</v-icon>
          {{ editingUser ? t('admin.users.editUser') : t('admin.users.createUser') }}
        </v-card-title>
        <v-card-text>
          <v-form ref="userForm" v-model="formValid">
            <v-text-field
              v-model="userFormData.username"
              :label="t('admin.users.username')"
              prepend-icon="mdi-account"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
              class="mb-3"
            />
            <v-text-field
              v-model="userFormData.email"
              :label="t('admin.users.email')"
              prepend-icon="mdi-email"
              :rules="[rules.required, rules.email]"
              variant="outlined"
              density="comfortable"
              class="mb-3"
            />
            <v-text-field
              v-model="userFormData.full_name"
              :label="t('admin.users.fullName')"
              prepend-icon="mdi-card-account-details"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
              class="mb-3"
            />
            <v-text-field
              v-if="!editingUser"
              v-model="userFormData.password"
              :label="t('admin.users.password')"
              prepend-icon="mdi-lock"
              :rules="[rules.required, rules.password]"
              :type="showPassword ? 'text' : 'password'"
              :append-inner-icon="showPassword ? 'mdi-eye' : 'mdi-eye-off'"
              @click:append-inner="showPassword = !showPassword"
              variant="outlined"
              density="comfortable"
              class="mb-3"
            />
            <v-select
              v-model="userFormData.role"
              :items="roleOptions"
              :label="t('common.role')"
              prepend-icon="mdi-shield-account"
              :rules="[rules.required]"
              variant="outlined"
              density="comfortable"
              class="mb-3"
            />
            <v-select
              v-model="userFormData.client_id_assigned"
              :items="clients"
              item-title="client_name"
              item-value="client_id"
              label="Assigned Client (optional)"
              prepend-icon="mdi-domain"
              variant="outlined"
              density="comfortable"
              clearable
            />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="userDialog = false">Cancel</v-btn>
          <v-btn color="primary" @click="saveUser" :loading="saving" :disabled="!formValid">
            {{ editingUser ? 'Update' : 'Create' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h6">
          <v-icon color="error" class="mr-2">mdi-alert</v-icon>
          Confirm Delete
        </v-card-title>
        <v-card-text>
          Are you sure you want to delete user <strong>{{ userToDelete?.username }}</strong>?
          This action cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Cancel</v-btn>
          <v-btn color="error" @click="deleteUser" :loading="deleting">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :color="snackbarColor" :timeout="3000">
      {{ snackbarMessage }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
import api from '@/services/api'

const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const search = ref('')
const roleFilter = ref(null)
const statusFilter = ref(null)
const users = ref([])
const clients = ref([])

const userDialog = ref(false)
const deleteDialog = ref(false)
const editingUser = ref(null)
const userToDelete = ref(null)
const formValid = ref(false)
const showPassword = ref(false)

const snackbar = ref(false)
const snackbarMessage = ref('')
const snackbarColor = ref('success')

const userFormData = ref({
  username: '',
  email: '',
  full_name: '',
  password: '',
  role: 'operator',
  client_id_assigned: null
})

const headers = [
  { title: 'Username', key: 'username', sortable: true },
  { title: 'Email', key: 'email', sortable: true },
  { title: 'Full Name', key: 'full_name', sortable: true },
  { title: 'Role', key: 'role', sortable: true },
  { title: 'Status', key: 'is_active', sortable: true },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center' }
]

const roleOptions = [
  { title: 'Admin', value: 'admin' },
  { title: 'Supervisor', value: 'poweruser' },
  { title: 'Operator', value: 'operator' }
]

const statusOptions = [
  { title: 'Active', value: true },
  { title: 'Inactive', value: false }
]

const rules = {
  required: v => !!v || 'This field is required',
  email: v => /.+@.+\..+/.test(v) || 'Invalid email address',
  password: v => (v && v.length >= 8) || 'Password must be at least 8 characters'
}

const filteredUsers = computed(() => {
  let result = users.value
  if (roleFilter.value) {
    result = result.filter(u => u.role === roleFilter.value)
  }
  if (statusFilter.value !== null) {
    result = result.filter(u => u.is_active === statusFilter.value)
  }
  return result
})

const showSnackbar = (message, color = 'success') => {
  snackbarMessage.value = message
  snackbarColor.value = color
  snackbar.value = true
}

const getRoleColor = (role) => {
  const colors = { admin: 'error', poweruser: 'warning', operator: 'info' }
  return colors[role] || 'grey'
}

const formatRole = (role) => {
  const labels = { admin: 'Admin', poweruser: 'Supervisor', operator: 'Operator' }
  return labels[role] || role
}

const formatDate = (date) => {
  if (!date) return t('common.na')
  return new Date(date).toLocaleDateString()
}

const refreshUsers = async () => {
  loading.value = true
  try {
    const response = await api.getUsers()
    users.value = response.data || []
  } catch (error) {
    console.error('Failed to load users:', error)
    showSnackbar('Failed to load users', 'error')
  } finally {
    loading.value = false
  }
}

const loadClients = async () => {
  try {
    const response = await api.getClients()
    clients.value = response.data || []
  } catch (error) {
    console.error('Failed to load clients:', error)
  }
}

const openCreateDialog = () => {
  editingUser.value = null
  userFormData.value = {
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'operator',
    client_id_assigned: null
  }
  userDialog.value = true
}

const editUser = (user) => {
  editingUser.value = user
  userFormData.value = {
    username: user.username,
    email: user.email,
    full_name: user.full_name,
    password: '',
    role: user.role,
    client_id_assigned: user.client_id_assigned
  }
  userDialog.value = true
}

const saveUser = async () => {
  saving.value = true
  try {
    if (editingUser.value) {
      await api.updateUser(editingUser.value.user_id, userFormData.value)
      showSnackbar('User updated successfully')
    } else {
      await api.createUser(userFormData.value)
      showSnackbar('User created successfully')
    }
    userDialog.value = false
    refreshUsers()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || 'Failed to save user', 'error')
  } finally {
    saving.value = false
  }
}

const toggleUserStatus = async (user) => {
  try {
    await api.updateUser(user.user_id, { is_active: !user.is_active })
    showSnackbar(`User ${user.is_active ? 'deactivated' : 'activated'} successfully`)
    refreshUsers()
  } catch (error) {
    showSnackbar('Failed to update user status', 'error')
  }
}

const confirmDelete = (user) => {
  userToDelete.value = user
  deleteDialog.value = true
}

const deleteUser = async () => {
  deleting.value = true
  try {
    await api.deleteUser(userToDelete.value.user_id)
    showSnackbar('User deleted successfully')
    deleteDialog.value = false
    refreshUsers()
  } catch (error) {
    showSnackbar('Failed to delete user', 'error')
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  refreshUsers()
  loadClients()
})
</script>
