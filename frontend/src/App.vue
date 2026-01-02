<template>
  <v-app>
    <v-app-bar app color="primary" dark v-if="isAuthenticated">
      <v-app-bar-title>Manufacturing KPI Platform</v-app-bar-title>

      <v-spacer></v-spacer>

      <v-btn text to="/">
        <v-icon left>mdi-view-dashboard</v-icon>
        Dashboard
      </v-btn>

      <v-btn text to="/production-entry">
        <v-icon left>mdi-clipboard-text</v-icon>
        Production Entry
      </v-btn>

      <v-btn text to="/kpi-dashboard">
        <v-icon left>mdi-chart-line</v-icon>
        KPI Dashboard
      </v-btn>

      <v-spacer></v-spacer>

      <v-menu offset-y>
        <template v-slot:activator="{ props }">
          <v-btn icon v-bind="props">
            <v-icon>mdi-account-circle</v-icon>
          </v-btn>
        </template>
        <v-list>
          <v-list-item>
            <v-list-item-title>{{ user?.full_name }}</v-list-item-title>
            <v-list-item-subtitle>{{ user?.role }}</v-list-item-subtitle>
          </v-list-item>
          <v-divider></v-divider>
          <v-list-item @click="handleLogout">
            <v-list-item-title>
              <v-icon left>mdi-logout</v-icon>
              Logout
            </v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
    </v-app-bar>

    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'

const router = useRouter()
const authStore = useAuthStore()

const isAuthenticated = computed(() => authStore.isAuthenticated)
const user = computed(() => authStore.currentUser)

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
/* Custom styles if needed */
</style>
