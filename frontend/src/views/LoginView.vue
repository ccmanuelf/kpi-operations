<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="4">
        <v-card class="elevation-12">
          <v-toolbar color="primary" dark flat>
            <v-toolbar-title>Manufacturing KPI Platform</v-toolbar-title>
          </v-toolbar>
          <v-card-text>
            <v-form @submit.prevent="handleLogin">
              <v-text-field
                v-model="username"
                label="Username"
                prepend-icon="mdi-account"
                type="text"
                required
                :error-messages="errors.username"
              ></v-text-field>

              <v-text-field
                v-model="password"
                label="Password"
                prepend-icon="mdi-lock"
                type="password"
                required
                :error-messages="errors.password"
              ></v-text-field>

              <v-alert v-if="errorMessage" type="error" class="mb-4" closable>
                {{ errorMessage }}
              </v-alert>
            </v-form>
          </v-card-text>
          <v-card-actions class="flex-column">
            <v-btn
              color="primary"
              @click="handleLogin"
              :loading="loading"
              block
              size="large"
              class="mb-3"
            >
              Login
            </v-btn>
            <div class="d-flex justify-space-between w-100 px-2">
              <v-btn
                variant="text"
                color="primary"
                size="small"
                @click="showForgotPassword = true"
              >
                Forgot Password?
              </v-btn>
              <v-btn
                variant="text"
                color="primary"
                size="small"
                @click="showRegister = true"
              >
                Create Account
              </v-btn>
            </div>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <!-- Forgot Password Dialog -->
    <v-dialog v-model="showForgotPassword" max-width="400">
      <v-card>
        <v-card-title class="text-h6">Reset Password</v-card-title>
        <v-card-text>
          <p class="mb-4">Enter your email address and we'll send you a link to reset your password.</p>
          <v-text-field
            v-model="resetEmail"
            label="Email Address"
            type="email"
            prepend-icon="mdi-email"
            :error-messages="resetErrors.email"
          ></v-text-field>
          <v-alert v-if="resetSuccess" type="success" class="mt-2">
            {{ resetSuccess }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn text @click="showForgotPassword = false">Cancel</v-btn>
          <v-btn color="primary" @click="handleForgotPassword" :loading="resetLoading">
            Send Reset Link
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Register Dialog -->
    <v-dialog v-model="showRegister" max-width="500">
      <v-card>
        <v-card-title class="text-h6">Create Account</v-card-title>
        <v-card-text>
          <v-form @submit.prevent="handleRegister">
            <v-text-field
              v-model="registerForm.username"
              label="Username"
              prepend-icon="mdi-account"
              :error-messages="registerErrors.username"
              required
            ></v-text-field>
            <v-text-field
              v-model="registerForm.email"
              label="Email"
              type="email"
              prepend-icon="mdi-email"
              :error-messages="registerErrors.email"
              required
            ></v-text-field>
            <v-text-field
              v-model="registerForm.full_name"
              label="Full Name"
              prepend-icon="mdi-badge-account"
              :error-messages="registerErrors.full_name"
              required
            ></v-text-field>
            <v-text-field
              v-model="registerForm.password"
              label="Password"
              type="password"
              prepend-icon="mdi-lock"
              :error-messages="registerErrors.password"
              hint="Min 8 chars, uppercase, lowercase, number, special char"
              required
            ></v-text-field>
            <v-text-field
              v-model="registerForm.confirmPassword"
              label="Confirm Password"
              type="password"
              prepend-icon="mdi-lock-check"
              :error-messages="registerErrors.confirmPassword"
              required
            ></v-text-field>
            <v-alert v-if="registerError" type="error" class="mt-2">
              {{ registerError }}
            </v-alert>
            <v-alert v-if="registerSuccess" type="success" class="mt-2">
              {{ registerSuccess }}
            </v-alert>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn text @click="showRegister = false">Cancel</v-btn>
          <v-btn color="primary" @click="handleRegister" :loading="registerLoading">
            Create Account
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import api from '@/services/api'

const router = useRouter()
const authStore = useAuthStore()

// Login state
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')
const errors = ref({})

// Forgot password state
const showForgotPassword = ref(false)
const resetEmail = ref('')
const resetLoading = ref(false)
const resetErrors = ref({})
const resetSuccess = ref('')

// Register state
const showRegister = ref(false)
const registerLoading = ref(false)
const registerError = ref('')
const registerSuccess = ref('')
const registerErrors = ref({})
const registerForm = reactive({
  username: '',
  email: '',
  full_name: '',
  password: '',
  confirmPassword: ''
})

const handleLogin = async () => {
  errors.value = {}
  errorMessage.value = ''

  if (!username.value) {
    errors.value.username = ['Username is required']
    return
  }

  if (!password.value) {
    errors.value.password = ['Password is required']
    return
  }

  loading.value = true

  const result = await authStore.login({
    username: username.value,
    password: password.value
  })

  loading.value = false

  if (result.success) {
    router.push('/')
  } else {
    errorMessage.value = result.error
  }
}

const handleForgotPassword = async () => {
  resetErrors.value = {}
  resetSuccess.value = ''
  
  if (!resetEmail.value) {
    resetErrors.value.email = ['Email is required']
    return
  }

  resetLoading.value = true
  
  try {
    await api.post('/api/auth/forgot-password', { email: resetEmail.value })
    resetSuccess.value = 'If your email is registered, you will receive a password reset link.'
    setTimeout(() => {
      showForgotPassword.value = false
      resetEmail.value = ''
      resetSuccess.value = ''
    }, 3000)
  } catch (error) {
    resetErrors.value.email = ['Failed to process request. Please try again.']
  } finally {
    resetLoading.value = false
  }
}

const handleRegister = async () => {
  registerErrors.value = {}
  registerError.value = ''
  registerSuccess.value = ''

  // Validate form
  if (!registerForm.username) {
    registerErrors.value.username = ['Username is required']
    return
  }
  if (!registerForm.email) {
    registerErrors.value.email = ['Email is required']
    return
  }
  if (!registerForm.full_name) {
    registerErrors.value.full_name = ['Full name is required']
    return
  }
  if (!registerForm.password) {
    registerErrors.value.password = ['Password is required']
    return
  }
  if (registerForm.password.length < 8) {
    registerErrors.value.password = ['Password must be at least 8 characters']
    return
  }
  if (registerForm.password !== registerForm.confirmPassword) {
    registerErrors.value.confirmPassword = ['Passwords do not match']
    return
  }

  registerLoading.value = true

  try {
    await api.post('/api/auth/register', {
      username: registerForm.username,
      email: registerForm.email,
      full_name: registerForm.full_name,
      password: registerForm.password,
      role: 'operator'
    })
    registerSuccess.value = 'Account created successfully! You can now login.'
    setTimeout(() => {
      showRegister.value = false
      Object.keys(registerForm).forEach(key => registerForm[key] = '')
      registerSuccess.value = ''
    }, 2000)
  } catch (error) {
    if (error.response?.data?.detail) {
      registerError.value = error.response.data.detail
    } else {
      registerError.value = 'Failed to create account. Please try again.'
    }
  } finally {
    registerLoading.value = false
  }
}
</script>
