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
              :label="t('admin.users.assignedClient')"
              prepend-icon="mdi-domain"
              variant="outlined"
              density="comfortable"
              clearable
            />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="userDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="saveUser" :loading="saving" :disabled="!formValid">
            {{ editingUser ? t('admin.users.saveUser') : t('admin.users.createUserBtn') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h6">
          <v-icon color="error" class="mr-2">mdi-alert</v-icon>
          {{ t('admin.users.confirmDeleteTitle') }}
        </v-card-title>
        <v-card-text>
          {{ t('admin.users.confirmDeleteText', { username: userToDelete?.username }) }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="error" @click="deleteUser" :loading="deleting">{{ t('common.delete') }}</v-btn>
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

const headers = computed(() => [
  { title: t('admin.users.username'), key: 'username', sortable: true },
  { title: t('admin.users.email'), key: 'email', sortable: true },
  { title: t('admin.users.fullName'), key: 'full_name', sortable: true },
  { title: t('common.role'), key: 'role', sortable: true },
  { title: t('common.status'), key: 'is_active', sortable: true },
  { title: t('admin.users.created'), key: 'created_at', sortable: true },
  { title: t('common.actions'), key: 'actions', sortable: false, align: 'center' }
])

const roleOptions = computed(() => [
  { title: t('admin.users.roleAdmin'), value: 'admin' },
  { title: t('admin.users.roleSupervisor'), value: 'poweruser' },
  { title: t('admin.users.roleOperator'), value: 'operator' }
])

const statusOptions = computed(() => [
  { title: t('admin.users.active'), value: true },
  { title: t('admin.users.inactive'), value: false }
])

const rules = {
  required: v => !!v || t('admin.users.fieldRequired'),
  email: v => /.+@.+\..+/.test(v) || t('admin.users.invalidEmail'),
  password: v => (v && v.length >= 8) || t('admin.users.passwordMinLength')
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
  const labels = { admin: t('admin.users.roleAdmin'), poweruser: t('admin.users.roleSupervisor'), operator: t('admin.users.roleOperator') }
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
    showSnackbar(t('admin.users.failedToLoadUsers'), 'error')
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
      showSnackbar(t('admin.users.userUpdated'))
    } else {
      await api.createUser(userFormData.value)
      showSnackbar(t('admin.users.userCreated'))
    }
    userDialog.value = false
    refreshUsers()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || t('admin.users.failedToSaveUser'), 'error')
  } finally {
    saving.value = false
  }
}

const toggleUserStatus = async (user) => {
  try {
    await api.updateUser(user.user_id, { is_active: !user.is_active })
    showSnackbar(user.is_active ? t('admin.users.userDeactivated') : t('admin.users.userActivated'))
    refreshUsers()
  } catch (error) {
    showSnackbar(t('admin.users.failedToUpdateStatus'), 'error')
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
    showSnackbar(t('admin.users.userDeleted'))
    deleteDialog.value = false
    refreshUsers()
  } catch (error) {
    showSnackbar(t('admin.users.failedToDeleteUser'), 'error')
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  refreshUsers()
  loadClients()
})
</script>
