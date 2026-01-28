<template>
  <v-container class="fill-height" fluid role="main" :aria-label="$t('auth.login')">
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="4">
        <v-card class="elevation-12" role="region" aria-labelledby="login-title">
          <v-toolbar color="primary" dark flat>
            <v-toolbar-title id="login-title">{{ $t('navigation.manufacturingKpi') }}</v-toolbar-title>
            <v-spacer></v-spacer>
            <LanguageToggle />
          </v-toolbar>
          <v-card-text>
            <v-form @submit.prevent="handleLogin" :aria-label="$t('auth.login')">
              <v-text-field
                v-model="username"
                :label="$t('auth.username')"
                prepend-icon="mdi-account"
                type="text"
                required
                :error-messages="errors.username"
                aria-required="true"
                :aria-invalid="!!errors.username"
                :aria-describedby="errors.username ? 'username-error' : undefined"
                autocomplete="username"
              ></v-text-field>
              <div v-if="errors.username" id="username-error" class="sr-only">{{ errors.username[0] }}</div>

              <v-text-field
                v-model="password"
                :label="$t('auth.password')"
                prepend-icon="mdi-lock"
                type="password"
                required
                :error-messages="errors.password"
                aria-required="true"
                :aria-invalid="!!errors.password"
                :aria-describedby="errors.password ? 'password-error' : undefined"
                autocomplete="current-password"
              ></v-text-field>
              <div v-if="errors.password" id="password-error" class="sr-only">{{ errors.password[0] }}</div>

              <v-alert v-if="errorMessage" type="error" class="mb-4" closable role="alert" aria-live="polite">
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
              :aria-label="$t('auth.loginButton')"
              :aria-busy="loading"
            >
              {{ $t('auth.loginButton') }}
            </v-btn>
            <div class="d-flex justify-space-between w-100 px-2">
              <v-btn
                variant="text"
                color="primary"
                size="small"
                @click="showForgotPassword = true"
                :aria-label="$t('auth.forgotPassword')"
              >
                {{ $t('auth.forgotPassword') }}
              </v-btn>
              <v-btn
                variant="text"
                color="primary"
                size="small"
                @click="showRegister = true"
                aria-label="Open account registration dialog"
              >
                {{ $t('common.add') }} {{ $t('admin.users') }}
              </v-btn>
            </div>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <!-- Forgot Password Dialog -->
    <v-dialog
      v-model="showForgotPassword"
      max-width="400"
      aria-labelledby="reset-password-title"
      role="dialog"
      aria-modal="true"
    >
      <v-card>
        <v-card-title id="reset-password-title" class="text-h6">{{ $t('auth.forgotPassword') }}</v-card-title>
        <v-card-text>
          <p id="reset-instructions" class="mb-4">{{ $t('auth.email') }}</p>
          <v-text-field
            v-model="resetEmail"
            :label="$t('auth.email')"
            type="email"
            prepend-icon="mdi-email"
            :error-messages="resetErrors.email"
            aria-required="true"
            :aria-invalid="!!resetErrors.email"
            aria-describedby="reset-instructions"
            autocomplete="email"
          ></v-text-field>
          <v-alert v-if="resetSuccess" type="success" class="mt-2" role="status" aria-live="polite">
            {{ resetSuccess }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn text @click="showForgotPassword = false" :aria-label="$t('common.cancel')">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="handleForgotPassword" :loading="resetLoading" :aria-busy="resetLoading">
            {{ $t('common.submit') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Register Dialog -->
    <v-dialog
      v-model="showRegister"
      max-width="500"
      aria-labelledby="register-title"
      role="dialog"
      aria-modal="true"
    >
      <v-card>
        <v-card-title id="register-title" class="text-h6">{{ $t('common.add') }} {{ $t('admin.users') }}</v-card-title>
        <v-card-text>
          <v-form @submit.prevent="handleRegister" aria-label="Registration form">
            <v-text-field
              v-model="registerForm.username"
              :label="$t('auth.username')"
              prepend-icon="mdi-account"
              :error-messages="registerErrors.username"
              required
              aria-required="true"
              :aria-invalid="!!registerErrors.username"
              autocomplete="username"
            ></v-text-field>
            <v-text-field
              v-model="registerForm.email"
              :label="$t('auth.email')"
              type="email"
              prepend-icon="mdi-email"
              :error-messages="registerErrors.email"
              required
              aria-required="true"
              :aria-invalid="!!registerErrors.email"
              autocomplete="email"
            ></v-text-field>
            <v-text-field
              v-model="registerForm.full_name"
              :label="$t('navigation.profile')"
              prepend-icon="mdi-badge-account"
              :error-messages="registerErrors.full_name"
              required
              aria-required="true"
              :aria-invalid="!!registerErrors.full_name"
              autocomplete="name"
            ></v-text-field>
            <v-text-field
              v-model="registerForm.password"
              :label="$t('auth.password')"
              type="password"
              prepend-icon="mdi-lock"
              :error-messages="registerErrors.password"
              :hint="$t('validation.minLength', { min: 8 })"
              required
              aria-required="true"
              :aria-invalid="!!registerErrors.password"
              aria-describedby="password-requirements"
              autocomplete="new-password"
            ></v-text-field>
            <span id="password-requirements" class="sr-only">{{ $t('validation.minLength', { min: 8 }) }}</span>
            <v-text-field
              v-model="registerForm.confirmPassword"
              :label="$t('common.confirm') + ' ' + $t('auth.password')"
              type="password"
              prepend-icon="mdi-lock-check"
              :error-messages="registerErrors.confirmPassword"
              required
              aria-required="true"
              :aria-invalid="!!registerErrors.confirmPassword"
              autocomplete="new-password"
            ></v-text-field>
            <v-alert v-if="registerError" type="error" class="mt-2" role="alert" aria-live="assertive">
              {{ registerError }}
            </v-alert>
            <v-alert v-if="registerSuccess" type="success" class="mt-2" role="status" aria-live="polite">
              {{ registerSuccess }}
            </v-alert>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn text @click="showRegister = false" :aria-label="$t('common.cancel')">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="handleRegister" :loading="registerLoading" :aria-busy="registerLoading">
            {{ $t('common.submit') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/authStore'
import api from '@/services/api'
import LanguageToggle from '@/components/LanguageToggle.vue'

const { t } = useI18n()

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
    await api.post('/auth/forgot-password', { email: resetEmail.value })
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
    await api.post('/auth/register', {
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
